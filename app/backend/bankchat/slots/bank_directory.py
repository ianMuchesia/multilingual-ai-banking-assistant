"""Which bank "we" are and which other banks / wallets exist, read from intent-router/config/bank.json."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BankDirectory:
    name: str
    own_bank_phrases: tuple[str, ...]
    other_banks: tuple[str, ...]
    wallets: tuple[str, ...]

    def mentions(self, text: str, phrases: tuple[str, ...]) -> list[str]:
        """Phrases that appear in `text` as whole words (case-insensitive), in catalog order, no duplicates."""
        lowered = text.lower()
        found = [p for p in phrases if re.search(rf"(?<![\w&]){re.escape(p)}(?![\w&])", lowered)]
        return list(dict.fromkeys(found))

    def other_banks_in(self, text: str) -> list[str]:
        return self.mentions(text, self.other_banks)

    def wallets_in(self, text: str) -> list[str]:
        return self.mentions(text, self.wallets)

    def mentions_own_bank(self, text: str) -> bool:
        return bool(self.mentions(text, (self.name.lower(),) + self.own_bank_phrases))

    def is_other_bank(self, name: str) -> bool:
        return name.strip().lower() in self.other_banks


def load_bank_directory(path: Path) -> BankDirectory:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BankDirectory(
        name=raw["name"],
        own_bank_phrases=tuple(p.lower() for p in raw["own_bank_phrases"]),
        other_banks=tuple(b.lower() for b in raw["other_banks"]),
        wallets=tuple(w.lower() for w in raw["wallets"]),
    )
