"""Loading the intent catalog and example sets."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LANGS = ("en", "sw", "sheng")


@dataclass(frozen=True)
class Example:
    text: str
    intent: str
    lang: str


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_intent_ids(path: Path) -> list[str]:
    """Intent ids from intents.json, in catalog order."""
    return [intent["id"] for intent in read_json(path)["intents"]]


def load_intent_categories(path: Path) -> dict[str, str]:
    """{intent id: category} from intents.json. Categories: view, action, info, none."""
    return {intent["id"]: intent["category"] for intent in read_json(path)["intents"]}


def load_examples(path: Path) -> list[Example]:
    """train.json / test.json ({intent: [{text, lang}, ...]}) -> flat list of Examples.

    Assumes the file is valid; run scripts.check_data first.
    """
    return [
        Example(text=item["text"], intent=intent, lang=item["lang"])
        for intent, items in read_json(path).items()
        for item in items
    ]


def normalize_text(text: str) -> str:
    """Lowercase and collapse whitespace, for duplicate and overlap checks."""
    return " ".join(text.split()).lower()
