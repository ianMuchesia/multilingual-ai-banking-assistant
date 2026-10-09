"""Validate intents.json, train.json, test.json and test_synthetic.json (if present). Exits 1 on failure.

    python -m scripts.check_data

Checks:
  - every intent in each file exists in intents.json, and every catalog intent has examples in each file
  - every example has a non-empty "text" and a "lang" of en / sw / sheng
  - no duplicate texts within a file, and no text in two files
    (case-insensitive, whitespace-normalised)
Prints example counts per intent and per language for each split.
"""

import sys
from collections import Counter, defaultdict
from typing import Any

from src.config import SPLITS, load_settings
from src.data import LANGS, load_intent_ids, normalize_text, read_json


def check_split(name: str, raw: Any, catalog: set[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Validate one split. Returns (errors, {normalised text: [intents it appears under]})."""
    if not isinstance(raw, dict):
        return [f"{name}: top level must map intent -> list of examples"], {}

    errors = [f"{name}: intent '{i}' is not in intents.json" for i in sorted(raw.keys() - catalog)]
    errors += [f"{name}: catalog intent '{i}' has no examples" for i in sorted(catalog - raw.keys())]

    seen: dict[str, list[str]] = defaultdict(list)
    for intent, items in raw.items():
        if not isinstance(items, list) or not items:
            errors.append(f"{name}: intent '{intent}' has no examples")
            continue
        for i, item in enumerate(items):
            where = f"{name}: {intent}[{i}]"
            text = item.get("text") if isinstance(item, dict) else None
            lang = item.get("lang") if isinstance(item, dict) else None
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{where}: missing or empty 'text'")
                continue
            if lang not in LANGS:
                errors.append(f"{where}: 'lang' must be one of {LANGS}, got {lang!r}")
            seen[normalize_text(text)].append(intent)

    errors += [
        f"{name}: duplicate text {text!r} under {', '.join(intents)}"
        for text, intents in seen.items()
        if len(intents) > 1
    ]
    return errors, seen


def overlap_errors(a_name: str, a: dict[str, list[str]], b_name: str, b: dict[str, list[str]]) -> list[str]:
    return [
        f"overlap: {text!r} in {a_name} ({', '.join(a[text])}) and {b_name} ({', '.join(b[text])})"
        for text in sorted(a.keys() & b.keys())
    ]


def format_counts(name: str, raw: dict[str, Any]) -> str:
    width = max(len(intent) for intent in raw)
    header = f"  {'intent':<{width}}  {'total':>5}  " + "  ".join(f"{lang:>5}" for lang in LANGS)
    lines = [name, header]
    totals: Counter[str] = Counter()
    for intent, items in raw.items():
        langs = Counter(item.get("lang") for item in items if isinstance(item, dict))
        totals.update(langs)
        lines.append(f"  {intent:<{width}}  {len(items):>5}  " + "  ".join(f"{langs[l]:>5}" for l in LANGS))
    total = sum(len(items) for items in raw.values())
    lines.append(f"  {'TOTAL':<{width}}  {total:>5}  " + "  ".join(f"{totals[l]:>5}" for l in LANGS))
    return "\n".join(lines)


def main() -> int:
    paths = load_settings().paths
    catalog = set(load_intent_ids(paths.intents))
    splits = [split for split in SPLITS if paths.examples(split).exists()]  # test_synthetic is optional
    raws = {split: read_json(paths.examples(split)) for split in splits}

    errors, texts = [], {}
    for split, raw in raws.items():
        split_errors, texts[split] = check_split(split, raw, catalog)
        errors += split_errors
    # No sentence may appear in two splits: train vs each exam, and the exams vs each other.
    for i, a in enumerate(splits):
        for b in splits[i + 1 :]:
            errors += overlap_errors(a, texts[a], b, texts[b])

    for name, raw in raws.items():
        if isinstance(raw, dict) and raw:
            print(format_counts(name, raw) + "\n")

    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        print("\n".join(f"  - {e}" for e in errors))
        return 1
    print("OK: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
