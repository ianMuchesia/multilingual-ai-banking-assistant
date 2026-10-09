"""Evaluate the router: tune its dials on held-out train scores, then score test ONCE.

The rule that keeps the test score honest: nothing is fitted or tuned on test.json.

    1. Held-out scores on train: every training example scored without having been
       seen (leave-one-out for similarity scorers, 5-fold CV for classifiers).
    2. Sweep threshold x margin on those scores, with the router's real decide() rules.
       Cosine scores and classifier probabilities use different grids.
    3. Choose the setting with zero critical errors and the highest coverage.
    4. Apply that one setting to the test set and report.

For a fine-tuned encoder (gemma-ft), step 1 is replaced: the encoder saw most of train,
so held-out scores on those sentences would be optimistic. Instead the scorer is fitted
on train minus the calibration split (sentences the encoder never saw) and the
calibration sentences are scored; steps 2-3 run on those. Step 4 is unchanged: the
scorer is refitted on all of train and the test set is scored once.

Error types, counted only for messages the router handled itself (not sent to llm):
    critical  wrong intent AND (predicted category is action OR true category is action
              OR true category is none). E.g. a help question sent to a transfer flow,
              two payment types mixed up, a fraud report not rejected.
    minor     any other wrong intent: view/info mix-ups, or a valid request rejected.

Works with any IntentScorer, so new scoring methods need no changes here.
"""

from collections import defaultdict
from dataclasses import dataclass, replace

import numpy as np

from src.config import FinetuneConfig, RouterConfig
from src.data import load_examples
from src.embeddings.gemma_ft import FinetuneMetadata
from src.index import EmbeddingIndex
from src.question_guard import question_markers
from src.router import Route, StaleIndexError, decide
from src.rules import BankConfig, apply_rules
from src.scoring import IntentScorer, Ranking, make_scorer

CRITICAL = "critical"
MINOR = "minor"
RISK_CURVE_PERCENTILES = (10, 30, 50, 70, 90)


def _grid(start: float, stop: float, step: float) -> np.ndarray:
    return np.round(np.arange(start, stop + 1e-9, step), 3)


# (thresholds, margins) per score scale. Cosine scores cluster tightly; probabilities spread over 0..1.
SWEEP_GRIDS = {
    "cosine": (_grid(0.50, 0.95, 0.01), _grid(0.0, 0.10, 0.005)),
    "probability": (_grid(0.10, 0.95, 0.01), _grid(0.0, 0.50, 0.02)),
}


# ---- data types ----

@dataclass(frozen=True)
class Case:
    """One message, already scored. Scoring happens once; the sweep only re-runs decide()."""

    text: str
    lang: str
    true_intent: str
    ranked: Ranking                    # after the rules, exactly what decide() sees in the live router
    markers: list[str]
    rule_reasons: list[str]

    @property
    def predicted(self) -> str:
        return self.ranked[0][0]

    @property
    def score(self) -> float:
        return self.ranked[0][1]

    @property
    def margin(self) -> float:
        return self.ranked[0][1] - self.ranked[1][1]


@dataclass(frozen=True)
class Outcome:
    case: Case
    route: Route
    reasons: list[str]
    error_type: str  # CRITICAL, MINOR, or "" (correct, or sent to llm)

    @property
    def correct(self) -> bool:
        return self.case.predicted == self.case.true_intent

    @property
    def covered(self) -> bool:
        return self.route != Route.LLM


@dataclass(frozen=True)
class Metrics:
    n: int
    top1_accuracy: float               # top intent correct, ignoring routing
    coverage: float                    # share NOT sent to llm
    accuracy_on_covered: float | None  # None when nothing was covered
    critical: int
    minor: int
    llm_rate: float
    llm_count: int
    llm_correct_top1: int              # sent to llm although the top intent was already right


@dataclass(frozen=True)
class SweepPoint:
    threshold: float
    margin: float
    metrics: Metrics


@dataclass(frozen=True)
class MethodResult:
    """Everything one scoring method produced: tuning on train, then the single test run."""

    backend: str
    model_id: str
    scorer: IntentScorer
    config: RouterConfig               # with the chosen threshold and margin
    found_zero_critical: bool
    train_metrics: Metrics             # held-out train, at the chosen setting
    test_outcomes: list[Outcome]
    test_metrics: Metrics
    test_by_language: dict[str, Metrics]
    test_confusion: dict[str, dict[str, int]]
    risk_curve: list[SweepPoint]       # held-out train, margin fixed
    calibrated: bool = False           # tuned on the calibration split instead of held-out train

    @property
    def held_out_method(self) -> str:
        if self.calibrated:
            return "calibration split"
        return "5-fold CV" if self.scorer.score_kind == "probability" else "leave-one-out"


# ---- building blocks ----

def build_cases(index: EmbeddingIndex, rankings: list[Ranking], bank: BankConfig | None) -> list[Case]:
    """Pair each row of `index` (text, language, true intent) with its ranking, after the rules (if `bank`)."""
    cases = []
    for text, lang, intent, ranked in zip(index.texts, index.langs, index.intents, rankings, strict=True):
        text = str(text)
        rule_reasons: list[str] = []
        if bank:
            ranked, rule_reasons = apply_rules(ranked, text, bank)
        cases.append(
            Case(
                text=text,
                lang=str(lang),
                true_intent=str(intent),
                ranked=ranked,
                markers=question_markers(text),
                rule_reasons=rule_reasons,
            )
        )
    return cases


def load_calibration(finetune: FinetuneConfig, train: EmbeddingIndex) -> set[str]:
    """Texts of the calibration split, after checking it belongs to this train index and fine-tuning run."""
    metadata = FinetuneMetadata.load(finetune.metadata_file)
    if metadata.train_sha256 != train.source_sha256:
        raise StaleIndexError(
            "train.json changed since fine-tuning, so the calibration split is stale. Run: python -m scripts.finetune"
        )
    if metadata.model_id != train.model_id:
        raise StaleIndexError(
            f"the train index was built with {train.model_id}, the current fine-tuned model is {metadata.model_id}. "
            "Rebuild the indexes with build_index --force."
        )
    texts = {ex.text for ex in load_examples(finetune.calibration_file)}
    if not texts:
        raise StaleIndexError(f"{finetune.calibration_file.name} is empty. Run: python -m scripts.finetune")
    return texts


def calibration_cases(
    method: str, train: EmbeddingIndex, calibration: set[str], k: int, bank: BankConfig | None
) -> list[Case]:
    """Fit on train minus the calibration sentences, score the calibration sentences."""
    in_calibration = np.isin(train.texts, list(calibration))
    found = int(in_calibration.sum())
    if found != len(calibration):
        raise ValueError(
            f"{len(calibration) - found} of {len(calibration)} calibration sentences are not in the train index; "
            "train.json changed since fine-tuning. Fine-tune again."
        )
    if found == len(train.texts):
        raise ValueError("the calibration split covers all of train; nothing left to fit the scorer on")

    def subset(mask: np.ndarray) -> EmbeddingIndex:
        return replace(
            train, vectors=train.vectors[mask], texts=train.texts[mask], intents=train.intents[mask],
            langs=train.langs[mask],
        )

    fit, held_out = subset(~in_calibration), subset(in_calibration)
    scorer = make_scorer(method, fit.vectors, fit.intents, k)
    return build_cases(held_out, [scorer.rank(v) for v in held_out.vectors], bank)


def error_type(predicted: str, true: str, categories: dict[str, str]) -> str:
    if predicted == true:
        return ""
    if categories[predicted] == "action" or categories[true] in ("action", "none"):
        return CRITICAL
    return MINOR


def judge(cases: list[Case], categories: dict[str, str], config: RouterConfig) -> list[Outcome]:
    outcomes = []
    for case in cases:
        route, reasons = decide(case.ranked, categories, config, case.markers)
        error = error_type(case.predicted, case.true_intent, categories) if route != Route.LLM else ""
        outcomes.append(Outcome(case=case, route=route, reasons=case.rule_reasons + reasons, error_type=error))
    return outcomes


def summarize(outcomes: list[Outcome]) -> Metrics:
    n = len(outcomes)
    covered = [o for o in outcomes if o.covered]
    to_llm = [o for o in outcomes if not o.covered]
    return Metrics(
        n=n,
        top1_accuracy=sum(o.correct for o in outcomes) / n,
        coverage=len(covered) / n,
        accuracy_on_covered=sum(o.correct for o in covered) / len(covered) if covered else None,
        critical=sum(o.error_type == CRITICAL for o in outcomes),
        minor=sum(o.error_type == MINOR for o in outcomes),
        llm_rate=len(to_llm) / n,
        llm_count=len(to_llm),
        llm_correct_top1=sum(o.correct for o in to_llm),
    )


def sweep(cases: list[Case], categories: dict[str, str], base: RouterConfig, score_kind: str) -> list[SweepPoint]:
    thresholds, margins = SWEEP_GRIDS[score_kind]
    points = []
    for threshold in thresholds:
        for margin in margins:
            config = replace(base, threshold=float(threshold), margin=float(margin))
            points.append(SweepPoint(float(threshold), float(margin), summarize(judge(cases, categories, config))))
    return points


def choose(points: list[SweepPoint]) -> tuple[SweepPoint, bool]:
    """Zero critical errors with the highest coverage (ties: larger margin, then higher threshold).

    Returns (point, found_zero). If no setting reaches zero critical errors,
    returns the one with the fewest, then the highest coverage.
    """
    safe = [p for p in points if p.metrics.critical == 0]
    if safe:
        return max(safe, key=lambda p: (p.metrics.coverage, p.margin, p.threshold)), True
    return min(points, key=lambda p: (p.metrics.critical, -p.metrics.coverage, -p.margin)), False


def per_language(outcomes: list[Outcome]) -> dict[str, Metrics]:
    groups: dict[str, list[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        groups[outcome.case.lang].append(outcome)
    return {lang: summarize(group) for lang, group in groups.items()}


def confusion(outcomes: list[Outcome], intents: list[str]) -> dict[str, dict[str, int]]:
    """{true intent: {predicted top-1 intent: count}}, every intent present in both dimensions."""
    matrix = {true: {pred: 0 for pred in intents} for true in intents}
    for outcome in outcomes:
        matrix[outcome.case.true_intent][outcome.case.predicted] += 1
    return matrix


def risk_curve(cases: list[Case], categories: dict[str, str], config: RouterConfig) -> list[SweepPoint]:
    """Coverage vs critical errors at 5 thresholds spread over the observed top scores, margin fixed."""
    top_scores = [case.score for case in cases]
    thresholds = sorted({round(float(np.percentile(top_scores, p)), 2) for p in RISK_CURVE_PERCENTILES})
    return [
        SweepPoint(t, config.margin, summarize(judge(cases, categories, replace(config, threshold=t))))
        for t in thresholds
    ]


def paired_counts(a: dict[str, bool], b: dict[str, bool]) -> tuple[int, int]:
    """On the sentences both were scored on: (A right and B wrong, B right and A wrong).

    One-sided counts like 9 vs 1 mean a real difference; 3 vs 2 is noise on 50 sentences.
    """
    shared = a.keys() & b.keys()
    return sum(a[t] and not b[t] for t in shared), sum(b[t] and not a[t] for t in shared)


# ---- the whole procedure for one scoring method ----

def run_method(
    backend: str,
    method: str,
    train: EmbeddingIndex,
    test: EmbeddingIndex,
    categories: dict[str, str],
    base: RouterConfig,
    bank: BankConfig | None,
    calibration: set[str] | None = None,
) -> MethodResult:
    """`bank` = None runs the scorer alone; with a BankConfig the rules run too (as in the live router).

    `calibration` = texts of train sentences the encoder never saw (fine-tuned backends only):
    the dials are then tuned on those, scored by a scorer fitted on the rest of train.
    """
    scorer = make_scorer(method, train.vectors, train.intents, base.k)
    config = replace(base, scoring=method, rules=bank is not None)

    # Tune on held-out train scores only (or on the calibration split).
    if calibration:
        train_cases = calibration_cases(method, train, calibration, base.k, bank)
    else:
        train_cases = build_cases(train, scorer.held_out_rankings(), bank)
    chosen, found_zero = choose(sweep(train_cases, categories, config, scorer.score_kind))
    config = replace(config, threshold=chosen.threshold, margin=chosen.margin)

    # Score test once, with the scorer fitted on all of train.
    test_outcomes = judge(build_cases(test, [scorer.rank(v) for v in test.vectors], bank), categories, config)

    return MethodResult(
        backend=backend,
        model_id=train.model_id,
        scorer=scorer,
        config=config,
        found_zero_critical=found_zero,
        train_metrics=chosen.metrics,
        test_outcomes=test_outcomes,
        test_metrics=summarize(test_outcomes),
        test_by_language=per_language(test_outcomes),
        test_confusion=confusion(test_outcomes, scorer.intents),
        risk_curve=risk_curve(train_cases, categories, config),
        calibrated=bool(calibration),
    )
