"""Evaluate the router: tune dials on held-out train scores, score test once, compare methods.

    python -m scripts.evaluate --backend gemma                              # all methods, exam: test.json
    python -m scripts.evaluate --backend gemma --test test_synthetic        # exam: test_synthetic.json
    python -m scripts.evaluate --backend gemini --scoring logreg

Held-out train scores: leave-one-out for max/topk_mean/centroid, 5-fold CV for logreg/mlp.
For gemma-ft (fine-tuned on train.json) the dials are tuned on the calibration split instead:
the scorer is fitted on train minus calibration and scores the calibration sentences.

Needs the train index and the chosen exam's index (built once; evaluation is then offline):
    python -m scripts.build_index --backend gemma
    python -m scripts.build_index --backend gemma --split test

Writes eval/results/{backend}_{scoring}.json and .csv (test.json), or
{backend}_{scoring}_test_synthetic.json and .csv, then compares every result saved for that exam.
"""

import argparse
import csv
import json
import logging
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from src.config import SCORING_METHODS, TEST_SPLITS, Settings, load_router_config, load_settings, with_overrides
from src.data import LANGS, load_intent_categories
from src.embeddings import BACKENDS, FINETUNED_BACKENDS
from src.evaluate import (
    CRITICAL,
    MethodResult,
    Metrics,
    Outcome,
    SweepPoint,
    load_calibration,
    paired_counts,
    run_method,
)
from src.index import EmbeddingIndex, file_sha256
from src.logging_setup import setup_logging
from src.router import StaleIndexError, check_index
from src.rules import load_bank_config

RESULTS_VERSION = 2  # older result files lack per-sentence data for paired counts

log = logging.getLogger("evaluate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune on train (leave-one-out), score test once.")
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--scoring", choices=("all", *SCORING_METHODS), default="all")
    parser.add_argument("--test", choices=TEST_SPLITS, default="test", help="which exam to score (default test)")
    parser.add_argument("--no-rules", action="store_true", help="scorer only, without the bank/statement rules")
    parser.add_argument("--dim", type=int, help="vector size of the indexes (default 768)")
    return parser.parse_args()


def results_name(backend: str, method: str, test_split: str, rules: bool = True) -> str:
    """gemma_logreg for test.json, plus _test_synthetic for the other exam and _norules without the rules."""
    name = f"{backend}_{method}" if test_split == "test" else f"{backend}_{method}_{test_split}"
    return name if rules else f"{name}_norules"


def method_label(r: dict) -> str:
    """'logreg', or 'logreg-norules' for a run without the rules."""
    return r["scoring"] if r.get("rules", False) else f"{r['scoring']}-norules"


# ---- loading ----

def load_indexes(
    settings: Settings, backend: str, test_split: str, categories: dict[str, str]
) -> tuple[EmbeddingIndex, EmbeddingIndex]:
    paths, dim = settings.paths, settings.embedding.dim
    indexes = []
    for split in ("train", test_split):
        build_cmd = f"python -m scripts.build_index --backend {backend} --split {split}"
        path = paths.index_file(backend, dim, split)
        if not path.exists():
            raise StaleIndexError(f"no {split} index at {path.name}. Run: {build_cmd}")
        index = EmbeddingIndex.load(path)
        check_index(index, file_sha256(paths.examples(split)), categories, build_cmd)
        indexes.append(index)

    train, test = indexes
    if (train.model_id, train.dim, train.prefix) != (test.model_id, test.dim, test.prefix):
        raise StaleIndexError(
            "train and test indexes were built with different model/dim/prefix. Rebuild both with --force."
        )
    return train, test


# ---- formatting ----

def pct(value: float | None) -> str:
    return "  n/a" if value is None else f"{value * 100:5.1f}%"


def metrics_rows(train: Metrics, test: Metrics) -> list[str]:
    rows = [
        ("top-1 accuracy", pct(train.top1_accuracy), pct(test.top1_accuracy)),
        ("coverage (not llm)", pct(train.coverage), pct(test.coverage)),
        ("accuracy on covered", pct(train.accuracy_on_covered), pct(test.accuracy_on_covered)),
        ("critical errors", str(train.critical), str(test.critical)),
        ("minor errors", str(train.minor), str(test.minor)),
        ("llm rate", pct(train.llm_rate), pct(test.llm_rate)),
        (
            "llm, top-1 already right",
            f"{train.llm_correct_top1}/{train.llm_count}",
            f"{test.llm_correct_top1}/{test.llm_count}",
        ),
    ]
    lines = [f"  {'':<26}{'train*':>10}{'test':>10}"]
    lines += [f"  {name:<26}{a:>10}{b:>10}" for name, a, b in rows]
    return lines


def language_rows(by_lang: dict[str, Metrics]) -> list[str]:
    lines = [f"  {'lang':<6}{'n':>4}{'top-1':>8}{'cover':>8}{'acc cov':>9}{'crit':>6}{'minor':>7}"]
    for lang in [l for l in LANGS if l in by_lang]:
        m = by_lang[lang]
        lines.append(
            f"  {lang:<6}{m.n:>4}{pct(m.top1_accuracy):>8}{pct(m.coverage):>8}"
            f"{pct(m.accuracy_on_covered):>9}{m.critical:>6}{m.minor:>7}"
        )
    return lines


def confusion_rows(matrix: dict[str, dict[str, int]]) -> list[str]:
    intents = list(matrix)
    width = max(len(i) for i in intents)
    corner = "true / predicted"
    lines = ["  columns: " + "  ".join(f"[{j}] {name}" for j, name in enumerate(intents))]
    lines.append(f"  {corner:<{width}}  " + "".join(f"{f'[{j}]':>5}" for j in range(len(intents))))
    for true in intents:
        cells = "".join(f"{(matrix[true][pred] or '.'):>5}" for pred in intents)
        lines.append(f"  {true:<{width}}  {cells}")
    return lines


def risk_rows(curve: list[SweepPoint]) -> list[str]:
    lines = [f"  {'threshold':>9}{'coverage':>10}{'acc cov':>9}{'critical':>10}"]
    lines += [
        f"  {p.threshold:>9.2f}{pct(p.metrics.coverage):>10}{pct(p.metrics.accuracy_on_covered):>9}{p.metrics.critical:>10}"
        for p in curve
    ]
    return lines


def critical_rows(outcomes: list[Outcome]) -> list[str]:
    critical = [o for o in outcomes if o.error_type == CRITICAL]
    if not critical:
        return ["  none"]
    return [
        f"  [{o.case.lang}] {o.case.text!r}: {o.case.true_intent} -> {o.case.predicted} ({o.route})"
        for o in critical
    ]


# ---- saving ----

def save_results(out_dir: Path, name: str, summary: dict, outcomes: list[Outcome]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "text", "lang", "true", "predicted", "route", "score", "margin", "reasons", "correct", "error_type",
            "train_sha8", "date",
        ])
        for o in outcomes:
            writer.writerow([
                o.case.text, o.case.lang, o.case.true_intent, o.case.predicted, str(o.route),
                f"{o.case.score:.4f}", f"{o.case.margin:.4f}", " | ".join(o.reasons), o.correct, o.error_type,
                summary["train_sha8"], summary["date"],
            ])


def load_saved_results(out_dir: Path, test_split: str) -> list[dict]:
    """Every result for this exam in the current format. Older files are skipped (rerun to refresh them)."""
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("*.json"))]
    results = [r for r in results if r.get("test_split", "test") == test_split]
    current = [r for r in results if r.get("version") == RESULTS_VERSION]
    if len(current) < len(results):
        print(f"  ({len(results) - len(current)} older result file(s) skipped: rerun that backend to refresh)")
    return current


def comparison_table(results: list[dict]) -> list[str]:
    """Every saved result side by side. train* = held-out train scores (LOO or 5-fold CV)."""
    header = (
        f"  {'train':<10}{'backend':<10}{'scoring':<18}{'thresh':>7}{'margin':>8}{'train* cov':>11}{'crit':>5}"
        f"{'top-1':>8}{'cover':>8}{'acc cov':>9}{'crit':>6}{'minor':>7}{'llm':>8}{'llm ok':>8}"
    )
    lines = [header]
    for r in results:
        loo, test = r["train_heldout"], r["test"]
        lines.append(
            f"  {r.get('train_sha8', '?'):<10}"
            f"{r['backend']:<10}{method_label(r):<18}{r['chosen']['threshold']:>7.2f}{r['chosen']['margin']:>8.3f}"
            f"{pct(loo['coverage']):>11}{loo['critical']:>5}"
            f"{pct(test['top1_accuracy']):>8}{pct(test['coverage']):>8}{pct(test['accuracy_on_covered']):>9}"
            f"{test['critical']:>6}{test['minor']:>7}{pct(test['llm_rate']):>8}"
            f"{test['llm_correct_top1']:>4}/{test['llm_count']:<3}"
        )
    return lines


def paired_table(results: list[dict]) -> list[str]:
    """Cell [row][col] = test sentences where ROW got top-1 right and COLUMN got it wrong.

    Compare a cell with its mirror: 9 vs 1 is a real difference, 3 vs 2 is noise.
    """
    names = [f"{r['backend']}/{method_label(r)}" for r in results]
    correct = [r["test_top1_correct"] for r in results]
    lines = ["  rows/columns: " + "  ".join(f"[{i}] {name}" for i, name in enumerate(names))]
    lines.append("       " + "".join(f"{f'[{j}]':>5}" for j in range(len(names))))
    for i, row in enumerate(correct):
        cells = "".join(
            f"{'-':>5}" if i == j else f"{paired_counts(row, col)[0]:>5}" for j, col in enumerate(correct)
        )
        lines.append(f"  [{i}]  {cells}")
    return lines


# ---- one scoring method ----

def print_report(r: MethodResult) -> None:
    cfg = r.config
    params = ", ".join(f"{k}={v}" for k, v in r.scorer.params.items())
    zero_note = "yes" if r.found_zero_critical else "NO: no setting reached zero; chose the fewest"
    print(
        "\n".join([
            f"\n=== {r.backend} / {cfg.scoring}{f' ({params})' if params else ''} ===",
            f"Chosen on train ({r.held_out_method}): threshold {cfg.threshold:.2f}, margin {cfg.margin:.3f}"
            f"  (zero critical errors on train: {zero_note})",
            f"* train = held-out scores ({r.held_out_method}); score scale: {r.scorer.score_kind}",
            "",
            *metrics_rows(r.train_metrics, r.test_metrics),
            "",
            "Test by language:",
            *language_rows(r.test_by_language),
            "",
            "Test confusion matrix (top-1 intent, ignoring routing):",
            *confusion_rows(r.test_confusion),
            "",
            "Critical errors on test (read these one by one):",
            *critical_rows(r.test_outcomes),
            "",
            f"Risk vs coverage on held-out train (margin fixed at {cfg.margin:.3f}):",
            *risk_rows(r.risk_curve),
        ])
    )


def result_summary(r: MethodResult, train_sha8: str, test_split: str) -> dict:
    cfg = r.config
    return {
        "version": RESULTS_VERSION,
        "test_split": test_split,          # which exam: test or test_synthetic
        "train_sha8": train_sha8,          # which train.json produced this result
        "date": date.today().isoformat(),
        "backend": r.backend,
        "scoring": cfg.scoring,
        "params": r.scorer.params,
        "held_out_method": r.held_out_method,
        "action_guard": cfg.action_guard,
        "rules": cfg.rules,
        "model_id": r.model_id,
        "chosen": {"threshold": cfg.threshold, "margin": cfg.margin, "zero_critical_found": r.found_zero_critical},
        "train_heldout": asdict(r.train_metrics),
        "test": asdict(r.test_metrics),
        "test_by_language": {lang: asdict(m) for lang, m in r.test_by_language.items()},
        "test_confusion": r.test_confusion,
        "test_top1_correct": {o.case.text: o.correct for o in r.test_outcomes},  # for paired counts
        "risk_curve_train": [{"threshold": p.threshold, "margin": p.margin, **asdict(p.metrics)} for p in r.risk_curve],
    }


def main() -> int:
    setup_logging()
    args = parse_args()
    settings = with_overrides(load_settings(), dim=args.dim)
    categories = load_intent_categories(settings.paths.intents)

    try:
        train, test = load_indexes(settings, args.backend, args.test, categories)
        # Fine-tuned encoders saw most of train: tune on the sentences they never saw.
        calibration = load_calibration(settings.finetune, train) if args.backend in FINETUNED_BACKENDS else None
    except (StaleIndexError, FileNotFoundError) as e:
        log.error("CANNOT START: %s", e)
        return 1
    if calibration:
        print(f"tuning on the calibration split: {len(calibration)} train sentences the encoder never saw")

    # Action guard always on in evaluation: it's part of the router being evaluated.
    base = replace(load_router_config(settings.paths.router_config, args.backend), action_guard=True)
    methods = SCORING_METHODS if args.scoring == "all" else (args.scoring,)
    train_sha8 = train.source_sha256[:8]  # the index was just checked against the current train.json
    print(
        f"{args.backend}: {len(train.texts)} train (train.json {train_sha8}), "
        f"{len(test.texts)} exam sentences ({args.test}), model {train.model_id}"
    )

    bank = None if args.no_rules else load_bank_config(settings.paths.bank_config)
    print(f"rules: {'OFF (scorer only)' if bank is None else f'on (bank: {bank.name})'}")

    out_dir = settings.paths.eval_results
    for method in methods:
        result = run_method(args.backend, method, train, test, categories, base, bank, calibration)
        print_report(result)
        name = results_name(args.backend, method, args.test, rules=bank is not None)
        save_results(out_dir, name, result_summary(result, train_sha8, args.test), result.test_outcomes)

    print(f"\n=== All saved results on exam '{args.test}' (dials chosen on held-out train) ===")
    saved = load_saved_results(out_dir, args.test)
    print("\n".join(comparison_table(saved)))
    print(f"\n=== Paired counts on exam '{args.test}': [row] right AND [column] wrong ===")
    print("\n".join(paired_table(saved)))
    print(f"\nPer-sentence details: eval/results/{results_name('<backend>', '<scoring>', args.test)}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
