"""Rules that run after the scorer, for details a model can't know.

The scorer decides WHAT kind of request a message is. Some distinctions depend on
facts, not on wording, and no amount of training data teaches them reliably:

    bank rule        is the destination Benki Yetu (internal) or another bank / wallet (external)?
                     A model can't know which bank "we" are; config/bank.json says so.
    statement rule   a statement sent to someone else (an email address, an accountant,
                     a landlord) is unsupported in v1, however much it looks like full_statement.

Rules only adjust the ranking. The router's confidence checks (threshold, margin)
still run afterwards, so a rule never makes an unsure message skip the LLM.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.scoring import Ranking

TRANSFER_PAIR = ("internal_transfer", "external_transfer")
STATEMENT_INTENTS = ("full_statement", "mini_statement")

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
THIRD_PARTY = re.compile(
    r"\b(to|for|kwa)\s+(my\s+|wangu\s+|yangu\s+)?"
    r"(accountant|landlord|lawyer|wakili|friend|rafiki|wife|husband|mke|mume|boss|employer|"
    r"mwenye\s+nyumba|brother|sister|kaka|dada|mzazi|parent)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BankConfig:
    name: str
    own_bank_phrases: tuple[str, ...]
    other_banks: tuple[str, ...]
    wallets: tuple[str, ...]


def load_bank_config(path: Path) -> BankConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BankConfig(
        name=raw["name"],
        own_bank_phrases=tuple(raw["own_bank_phrases"]),
        other_banks=tuple(raw["other_banks"]),
        wallets=tuple(raw["wallets"]),
    )


def _mentions(text: str, phrases: tuple[str, ...]) -> list[str]:
    """Phrases that appear in `text` as whole words (case-insensitive)."""
    lowered = text.lower()
    found = [p for p in phrases if re.search(rf"(?<![\w&]){re.escape(p)}(?![\w&])", lowered)]
    return list(dict.fromkeys(found))


def transfer_destination(text: str, bank: BankConfig) -> tuple[str | None, list[str]]:
    """("external_transfer" | "internal_transfer" | None, the words that decided it).

    Another bank or a wallet wins over own-bank words: "Absa hapa hapa" still leaves Benki Yetu.
    """
    elsewhere = _mentions(text, bank.other_banks + bank.wallets)
    if elsewhere:
        return "external_transfer", elsewhere
    own = _mentions(text, (bank.name.lower(),) + bank.own_bank_phrases)
    if own:
        return "internal_transfer", own
    return None, []


def is_third_party_statement(text: str) -> bool:
    return bool(EMAIL.search(text) or THIRD_PARTY.search(text))


def _promote(ranked: Ranking, intent: str, score: float, drop: tuple[str, ...]) -> Ranking:
    """`intent` first with `score`; `drop` intents removed so the margin is measured against a real alternative."""
    return [(intent, score)] + [(i, s) for i, s in ranked if i != intent and i not in drop]


def apply_rules(ranked: Ranking, text: str, bank: BankConfig) -> tuple[Ranking, list[str]]:
    """Adjust the ranking for facts the scorer can't know. Returns (ranking, reasons)."""
    top, score = ranked[0]

    if top in TRANSFER_PAIR:
        destination, words = transfer_destination(text, bank)
        if destination:
            # The scorer decided "it's a transfer"; the rule decides which kind. The margin is then
            # measured against the best NON-transfer intent.
            reason = f"bank rule: mentions {', '.join(words)} -> {destination}"
            if destination != top:
                reason += f" (scorer said {top})"
            return _promote(ranked, destination, score, drop=TRANSFER_PAIR), [reason]

    if top in STATEMENT_INTENTS and is_third_party_statement(text):
        return _promote(ranked, "unsupported", score, drop=()), [
            f"statement rule: {top} for someone else (email address or third party) -> unsupported"
        ]

    return ranked, []
