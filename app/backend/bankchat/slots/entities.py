"""Rule-based entity extraction from one customer message.

Order matters. Each kind of number is found and blanked out before the next is looked for:
references -> till/paybill (+ paybill account) -> labelled account numbers ("account 0123...")
-> phone numbers -> other long numbers (account numbers) -> dates. The amount is read last,
from what is left, so a phone or account number is never mistaken for an amount.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from bankchat.domain import AccountType
from bankchat.slots.amounts import find_amount
from bankchat.slots.bank_directory import BankDirectory
from bankchat.slots.dates import mask_dates

# Kenyan mobile numbers: 07xx / 01xx, 2547xx / 2541xx, +254 7xx, with optional spaces or dashes.
_PHONE = re.compile(r"(?<![\d+])(?:\+?254[\s-]?|0)([17]\d{2})[\s-]?(\d{3})[\s-]?(\d{3})(?!\d)")
# Transaction references as printed on receipts: two letters + 8 letters/digits, upper case.
_REFERENCE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{8})\b")
_CURRENCY_CODES = ("KES", "KSH")
_TILL = re.compile(r"\b(?:till|buy\s*goods)(?:\s*(?:number|no\.?|#|namba))?\s*:?\s*(\d{5,8})\b", re.I)
_PAYBILL = re.compile(
    r"\b(?:pay\s*bill|business)(?:\s*(?:number|no\.?|#|namba))?\s*:?\s*(\d{5,7})\b", re.I
)
_PAYBILL_ACCOUNT = re.compile(
    r"(?<!current\s)(?<!savings\s)(?<!saving\s)\b(?:account|acc|acct|a/c)(?:\s*(?:number|no\.?|#|namba))?\s*:?\s*([A-Za-z0-9-]*\d[A-Za-z0-9-]*)\b", re.I
)
_LABELLED_ACCOUNT = re.compile(
    r"\b(?:account|acc|acct|a/c)(?:\s*(?:number|no\.?|#|namba))?\s*:?\s*(\d{6,20})(?!\d)", re.I
)
_ACCOUNT_NUMBER = re.compile(r"(?<!\d)(\d{8,16})(?!\d)")

_SAVINGS = r"(?:savings?|akiba)"
_CURRENT = r"(?:current|checking)"
_TYPE = rf"(?:{_SAVINGS}|{_CURRENT})"
_FROM_HINT = re.compile(rf"\b(?:from|kutoka|out of)\s+(?:my\s+|the\s+)?({_TYPE})", re.I)
_TO_HINT = re.compile(rf"\b(?:to|into|kwa|kwenye|in)\s+(?:my\s+|the\s+)?({_TYPE})", re.I)
_PAIR_HINT = re.compile(rf"\b({_TYPE})\s+(?:account\s+)?(?:to|into|kwa|->)\s+(?:my\s+)?({_TYPE})", re.I)
_ANY_TYPE = re.compile(rf"\b({_TYPE})\b", re.I)
_OWN_WALLET = re.compile(
    r"\bmy\s+(?:own\s+)?(?:m-?pesa|phone|number|line|simu)\b|\b(?:m-?pesa|namba|nambari|simu)\s+(?:yangu|yako)\b",
    re.I,
)
_RECEIVED = re.compile(r"\b(received|receive|came in|come in|credited|incoming|got|sent me|nilipokea|nimepokea|imeingia)\b", re.I)
_SENT = re.compile(r"\b(sent(?!\s+me\b)|paid|transferred|outgoing|debited|nilituma|nimetuma|nililipa)\b", re.I)


@dataclass(frozen=True)
class MessageEntities:
    amount: Decimal | None = None
    phones: list[str] = field(default_factory=list)          # normalised 2547XXXXXXXX
    account_numbers: list[str] = field(default_factory=list)
    till: str | None = None
    paybill: str | None = None
    paybill_account: str | None = None
    references: list[str] = field(default_factory=list)
    other_banks: list[str] = field(default_factory=list)
    wallets: list[str] = field(default_factory=list)
    own_bank: bool = False
    own_wallet: bool = False
    from_hint: AccountType | None = None
    to_hint: AccountType | None = None
    account_hint: AccountType | None = None                  # any savings/current mention
    direction_hint: str | None = None                        # "in" | "out"


def normalize_phone(raw: str) -> str | None:
    """Any accepted Kenyan mobile format -> 2547XXXXXXXX / 2541XXXXXXXX, else None."""
    match = _PHONE.fullmatch(raw.strip())
    if not match:
        return None
    return "254" + "".join(match.groups())


def _account_type(word: str) -> AccountType:
    return AccountType.SAVINGS if re.fullmatch(_SAVINGS, word, re.I) else AccountType.CURRENT


def _blank(text: str, pattern: re.Pattern[str]) -> str:
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def _account_hints(text: str) -> tuple[AccountType | None, AccountType | None, AccountType | None]:
    from_hint = to_hint = None
    if pair := _PAIR_HINT.search(text):
        from_hint, to_hint = _account_type(pair.group(1)), _account_type(pair.group(2))
    if from_hint is None and (match := _FROM_HINT.search(text)):
        from_hint = _account_type(match.group(1))
    if to_hint is None and (match := _TO_HINT.search(text)):
        to_hint = _account_type(match.group(1))
    any_match = _ANY_TYPE.search(text)
    return from_hint, to_hint, _account_type(any_match.group(1)) if any_match else None


def _direction(text: str) -> str | None:
    received, sent = bool(_RECEIVED.search(text)), bool(_SENT.search(text))
    if received and not sent:
        return "in"
    if sent and not received:
        return "out"
    return None


def _mask_span(text: str, match: re.Match[str]) -> str:
    start, end = match.span()
    return text[:start] + " " * (end - start) + text[end:]


def extract_entities(text: str, bank: BankDirectory) -> MessageEntities:
    references = [
        m.group(1)
        for m in _REFERENCE.finditer(text)
        if any(c.isdigit() for c in m.group(1)) and not m.group(1).startswith(_CURRENCY_CODES)
    ]
    masked = text
    for reference in references:
        masked = masked.replace(reference, " " * len(reference))

    till_match = _TILL.search(masked)
    paybill_match = _PAYBILL.search(masked)
    masked = _blank(_blank(masked, _TILL), _PAYBILL)

    paybill_account = None
    if paybill_match and (acc_match := _PAYBILL_ACCOUNT.search(masked)):
        paybill_account = acc_match.group(1)
        masked = _mask_span(masked, acc_match)

    # "account 0123456789" is a bank account even though it also looks like an 01xx phone number.
    account_numbers = [m.group(1) for m in _LABELLED_ACCOUNT.finditer(masked)]
    masked = _blank(masked, _LABELLED_ACCOUNT)

    phones = list(dict.fromkeys("254" + "".join(m.groups()) for m in _PHONE.finditer(masked)))
    masked = _blank(masked, _PHONE)

    account_numbers = list(dict.fromkeys(account_numbers + [m.group(1) for m in _ACCOUNT_NUMBER.finditer(masked)]))
    masked = mask_dates(_blank(masked, _ACCOUNT_NUMBER))

    from_hint, to_hint, account_hint = _account_hints(text)
    return MessageEntities(
        amount=find_amount(masked),
        phones=phones,
        account_numbers=account_numbers,
        till=till_match.group(1) if till_match else None,
        paybill=paybill_match.group(1) if paybill_match else None,
        paybill_account=paybill_account,
        references=references,
        other_banks=bank.other_banks_in(text),
        wallets=bank.wallets_in(text),
        own_bank=bank.mentions_own_bank(text),
        own_wallet=bool(_OWN_WALLET.search(text)),
        from_hint=from_hint,
        to_hint=to_hint,
        account_hint=account_hint,
        direction_hint=_direction(text),
    )
