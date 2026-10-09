"""Amounts in customer messages: "5k", "5,000", "1.5M", "KES 2,400", "sh 300", "5 thao", "elfu tano".

`find_amount` expects text in which phone numbers, account numbers, till/paybill numbers,
references and dates have already been masked (see entities.py), so their digits are
never mistaken for an amount.
"""

import re
from decimal import Decimal, InvalidOperation

MULTIPLIERS: dict[str, Decimal] = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "thao": Decimal(1_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
}

_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d+)?"
_CURRENCY = r"(?:kes|kshs?|shs?)"

# Ordered from most to least explicit; the first pattern that matches wins.
_CURRENCY_PREFIXED = re.compile(
    rf"(?<![\w]){_CURRENCY}\s*\.?\s*({_NUMBER})\s*(k|m|mn|million|thousand)?(?![\w-])", re.IGNORECASE
)
_SUFFIXED_WORD = re.compile(rf"(?<![\w.,])({_NUMBER})\s*(thousand|million|mn|thao)\b", re.IGNORECASE)
_SUFFIXED_LETTER = re.compile(rf"(?<![\w.,])({_NUMBER})(k|m)(?![\w-])", re.IGNORECASE)
_CURRENCY_SUFFIXED = re.compile(rf"(?<![\w.,])({_NUMBER})\s*(?:/=|bob\b|{_CURRENCY}(?![\w]))", re.IGNORECASE)
_GROUPED = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)(?![\w,])")
_PLAIN = re.compile(r"(?<![\w.,])(\d{1,7}(?:\.\d{1,2})?)(?![\w,]|\.\d)")

# Swahili number words, for "elfu tano" (5,000), "laki moja" (100,000), "mia tano" (500).
SWAHILI_UNITS: dict[str, int] = {
    "moja": 1, "mbili": 2, "tatu": 3, "nne": 4, "tano": 5, "sita": 6, "saba": 7, "nane": 8, "tisa": 9,
    "kumi": 10, "ishirini": 20, "thelathini": 30, "arobaini": 40, "hamsini": 50,
    "sitini": 60, "sabini": 70, "themanini": 80, "tisini": 90,
}
SWAHILI_SCALES: dict[str, int] = {"mia": 100, "elfu": 1_000, "laki": 100_000, "milioni": 1_000_000}
_SWAHILI = re.compile(
    rf"\b({'|'.join(SWAHILI_SCALES)})\s+({'|'.join(SWAHILI_UNITS)})(?:\s+na\s+({'|'.join(SWAHILI_UNITS)}))?\b",
    re.IGNORECASE,
)


def _to_decimal(number: str) -> Decimal | None:
    try:
        return Decimal(number.replace(",", ""))
    except InvalidOperation:
        return None


def _scaled(number: str, suffix: str | None) -> Decimal | None:
    value = _to_decimal(number)
    if value is None:
        return None
    if suffix:
        value *= MULTIPLIERS[suffix.lower()]
    return value.quantize(Decimal("0.01"))


def _swahili_amount(text: str) -> Decimal | None:
    match = _SWAHILI.search(text)
    if not match:
        return None
    scale, unit, extra = match.group(1).lower(), match.group(2).lower(), match.group(3)
    units = SWAHILI_UNITS[unit] + (SWAHILI_UNITS[extra.lower()] if extra else 0)
    return Decimal(SWAHILI_SCALES[scale] * units).quantize(Decimal("0.01"))


def find_amount(masked_text: str) -> Decimal | None:
    """The first amount in the message, most explicit form first. None if there is none or it is zero."""
    for pattern in (_CURRENCY_PREFIXED, _SUFFIXED_WORD, _SUFFIXED_LETTER, _CURRENCY_SUFFIXED):
        match = pattern.search(masked_text)
        if match:
            suffix = match.group(2) if pattern.groups >= 2 else None
            value = _scaled(match.group(1), suffix)
            if value:
                return value
    swahili = _swahili_amount(masked_text)
    if swahili:
        return swahili
    for pattern in (_GROUPED, _PLAIN):
        match = pattern.search(masked_text)
        if match:
            value = _scaled(match.group(1), None)
            if value:
                return value
    return None
