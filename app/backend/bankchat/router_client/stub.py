"""A keyword stand-in for the real router (ROUTER_MODE=stub): no model, same output shape.

Good enough for frontend development, CI and tests. It mimics the real router's policy:
a confidence threshold and margin, the bank rule for transfers, the action guard
(money-moving intent phrased as a question -> llm), and reject for unsupported requests.
Its scores are keyword counts mapped onto 0..1, not similarities.
"""

import logging
import re
import time

from bankchat.domain import Category, Intent, RouteName, category_of
from bankchat.router_client.base import RouterDecision
from bankchat.slots.bank_directory import BankDirectory

log = logging.getLogger(__name__)

THRESHOLD = 0.65
MARGIN = 0.10
BASE_SCORE = 0.55
SCORE_PER_HIT = 0.15
MAX_SCORE = 0.97
FLOOR_SCORE = 0.05
HELP_QUESTION_BONUS_HITS = 2
TOP_INTENTS = 3

_TRANSFER_VERB = r"\b(send|tuma|transfer|move|hamisha|withdraw|toa)\b"
_PHONE = r"(?<!\d)(?:\+?254|0)[17]\d{2}[\s-]?\d{3}[\s-]?\d{3}(?!\d)"

# intent -> keyword patterns; each matching pattern is one "hit". Order breaks ties.
KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.BALANCE_INQUIRY: (
        r"\bbalance\b", r"\bsalio\b", r"\bhow much (money )?(do i have|is (in|on|left))",
        r"\bpesa ngapi\b", r"\bnina pesa\b", r"\bavailable\b",
    ),
    Intent.MINI_STATEMENT: (
        r"\bmini[\s-]?statement\b", r"\brecent (transactions|activity)\b",
        r"\blast (few|\d+|ten|five) transactions\b", r"\btransaction history\b", r"\bhivi karibuni\b",
    ),
    Intent.FULL_STATEMENT: (
        r"(?<!mini )(?<!mini-)\bstatement\b", r"\bpdf\b", r"\b\d+\s+months?\b", r"\btaarifa ya akaunti\b",
        r"\bmiezi\b",
    ),
    Intent.FIND_TRANSACTION: (
        r"\bdid\b.*\b(come|arrive|receive|reach|go through)\b", r"\bsalary\b", r"\b(find|search|look for|trace)\b",
        r"\bsent me\b", r"\bimeingia\b", r"\bnilituma\b", r"\bstatus of\b",
    ),
    Intent.VIEW_RECEIPT: (
        r"\breceipt\b", r"\bproof of payment\b", r"\brisiti\b", r"\bpayment proof\b", r"\bconfirmation (message|slip)\b",
    ),
    Intent.INTERNAL_TRANSFER: (
        _TRANSFER_VERB, r"\b(savings?|current|akiba)\b", r"\b(benki yetu|same bank|this bank|hapa hapa)\b",
        r"(?<!\d)1[12]\d{10}(?!\d)",
    ),
    Intent.EXTERNAL_TRANSFER: (
        _TRANSFER_VERB, r"\bpesalink\b", r"\b(another|other) bank\b", _PHONE,
    ),
    Intent.LIPA_NA_MPESA: (
        r"\b(pay|lipa)\b", r"\btill\b", r"\bpay\s*bill\b", r"\bbuy goods\b", r"\blipa na m-?pesa\b",
    ),
    Intent.TRANSFER_HELP: (
        r"\blimits?\b", r"\b(charges?|fees?|cost)\b", r"\bhow long\b", r"\bhow (do|can) i\b", r"\bhow to\b",
        r"\bjinsi ya\b", r"\b(rtgs|eft)\b",
    ),
    Intent.UNSUPPORTED: (
        r"\b(loan|mkopo)\b", r"\b(card|atm|pin)\b", r"\bopen (an? )?account\b", r"^\s*(hello|hi|hey|habari|niaje|sasa)\b",
        r"\b(scam|fraud|stolen|complain|complaint)\b", r"\b(weather|joke|football)\b",
    ),
}
_COMPILED = {intent: [re.compile(p, re.I) for p in patterns] for intent, patterns in KEYWORDS.items()}
_ORDER = list(KEYWORDS)

# Same idea as intent-router/src/question_guard.py.
QUESTION_WORDS = frozenset({"how", "what", "jinsi", "aje", "gani", "ngapi"})
QUESTION_PHRASES = (("can", "i"), ("is", "there"))
JE_SUFFIX = "je"
JE_MIN_LENGTH = 5


def question_markers(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    found = ["?"] if "?" in text else []
    found += [w for w in words if w in QUESTION_WORDS]
    found += [f"{a} {b}" for a, b in QUESTION_PHRASES if (a, b) in set(zip(words, words[1:]))]
    found += [w for w in words if len(w) >= JE_MIN_LENGTH and w.endswith(JE_SUFFIX)]
    return list(dict.fromkeys(found))


def _score(hits: int) -> float:
    return min(MAX_SCORE, BASE_SCORE + SCORE_PER_HIT * hits) if hits else FLOOR_SCORE


class StubRouterClient:
    mode = "stub"

    def __init__(self, bank: BankDirectory) -> None:
        self._bank = bank

    def _hits(self, text: str, markers: list[str]) -> dict[Intent, list[str]]:
        hits = {intent: [p.pattern for p in patterns if p.search(text)] for intent, patterns in _COMPILED.items()}
        if hits[Intent.TRANSFER_HELP] and markers:
            hits[Intent.TRANSFER_HELP] += ["question"] * HELP_QUESTION_BONUS_HITS
        wallet_or_bank = self._bank.other_banks_in(text) + self._bank.wallets_in(text)
        hits[Intent.EXTERNAL_TRANSFER] += [f"mentions {name}" for name in wallet_or_bank]
        return hits

    def _bank_rule(self, ranked: list[tuple[str, float]], text: str) -> tuple[list[tuple[str, float]], list[str]]:
        top, score = ranked[0]
        pair = (Intent.INTERNAL_TRANSFER.value, Intent.EXTERNAL_TRANSFER.value)
        if top not in pair:
            return ranked, []
        elsewhere = self._bank.other_banks_in(text) + self._bank.wallets_in(text)
        if elsewhere or re.search(_PHONE, text):
            destination = Intent.EXTERNAL_TRANSFER.value
        elif self._bank.mentions_own_bank(text) or re.search(r"\b(savings?|current|akiba)\b", text, re.I):
            destination = Intent.INTERNAL_TRANSFER.value
        else:
            return ranked, []
        rest = [(i, s) for i, s in ranked if i not in pair]
        return [(destination, score)] + rest, [f"bank rule (stub): destination -> {destination}"]

    def route(self, text: str) -> RouterDecision:
        started = time.perf_counter()
        markers = question_markers(text)
        hits = self._hits(text, markers)
        matched = any(hits.values())

        def order(pair: tuple[str, float]) -> tuple[float, bool, int]:
            # With no keyword at all, "unsupported" is the honest best guess.
            fallback_first = not matched and pair[0] == Intent.UNSUPPORTED
            return -pair[1], not fallback_first, _ORDER.index(Intent(pair[0]))

        ranked = sorted(((intent.value, _score(len(found))) for intent, found in hits.items()), key=order)
        ranked, rule_reasons = self._bank_rule(ranked, text)
        route, reasons = self._decide(ranked, markers, matched=matched)
        top, best = ranked[0]
        nearest = [(f"keyword: {p}", top, best) for p in hits[Intent(top)]][:TOP_INTENTS]
        decision = RouterDecision(
            intent=top,
            route=route.value,
            score=best,
            margin=best - ranked[1][1],
            top3=ranked[:TOP_INTENTS],
            nearest_examples=nearest,
            reasons=["stub router: keyword rules, not the model"] + rule_reasons + reasons,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        log.debug("stub route %r -> %s %s", text, decision.intent, decision.route)
        return decision

    @staticmethod
    def _decide(ranked: list[tuple[str, float]], markers: list[str], matched: bool) -> tuple[RouteName, list[str]]:
        (top, best), (second, runner_up) = ranked[0], ranked[1]
        category = category_of(top)
        reasons = [f"best intent: {top} ({category}), score {best:.3f}"]
        if not matched:
            return RouteName.LLM, reasons + ["no keyword matched"]
        uncertain = []
        if best < THRESHOLD:
            uncertain.append(f"low confidence: {best:.3f} < threshold {THRESHOLD:.2f}")
        if best - runner_up < MARGIN:
            uncertain.append(f"ambiguous between {top} and {second}: margin {best - runner_up:.3f} < {MARGIN:.3f}")
        if uncertain:
            return RouteName.LLM, reasons + uncertain
        if category is Category.ACTION and markers:
            return RouteName.LLM, reasons + [f"action intent but phrased as a question (found: {', '.join(markers)})"]
        if category is Category.NONE:
            return RouteName.REJECT, reasons + ["outside the supported catalog"]
        if category is Category.ACTION:
            return RouteName.CONFIRM, reasons + ["moves money: customer must confirm"]
        return RouteName.DIRECT, reasons + [f"{category} intent: safe to answer directly"]
