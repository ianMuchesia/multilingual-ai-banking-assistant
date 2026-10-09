"""Simple date ranges in messages: "last 3 months", "last month", "yesterday", "jana",
"from 1/3/2026 to 31/3/2026", "march", "since january", "miezi sita".

Anything more ambitious belongs to the (future) LLM step. `mask_dates` blanks these
phrases so their digits are not read as amounts.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS: dict[str, int] = {
    name: number
    for number in range(1, 13)
    for name in (calendar.month_name[number].lower(), calendar.month_abbr[number].lower())
}
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))

UNIT_DAYS = {"day": 1, "week": 7}
SWAHILI_MONTH_COUNTS: dict[str, int] = {
    "mmoja": 1, "miwili": 2, "mitatu": 3, "minne": 4, "mitano": 5, "sita": 6, "saba": 7, "kumi na mbili": 12,
}
WORD_NUMBERS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a": 1,
}
_COUNT = rf"(\d{{1,2}}|{'|'.join(WORD_NUMBERS)})"

_ISO = r"\d{4}-\d{1,2}-\d{1,2}"
_DMY = r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
_DAY_MONTH = rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTH_NAMES})\b(?:,?\s+\d{{4}})?"
_MONTH_DAY = rf"(?:{_MONTH_NAMES})\s+\d{{1,2}}(?:st|nd|rd|th)?\b(?:,?\s+\d{{4}})?"
_EXPLICIT = rf"(?:{_ISO}|{_DMY}|{_DAY_MONTH}|{_MONTH_DAY})"

_RANGE = re.compile(rf"\b(?:from|between|kutoka)\s+({_EXPLICIT})\s+(?:to|and|until|till|hadi|mpaka|-)\s+({_EXPLICIT})", re.I)
_LAST_N = re.compile(rf"\b(?:last|past|previous|the last)\s+{_COUNT}\s+(day|week|month|year)s?\b", re.I)
_N_AGO = re.compile(rf"\b{_COUNT}\s+(day|week|month)s?\s+ago\b", re.I)
_SW_MONTHS = re.compile(rf"\bmiezi\s+({'|'.join(SWAHILI_MONTH_COUNTS)})\b", re.I)
_LAST_PERIOD = re.compile(r"\b(?:last|previous)\s+(week|month|year)\b|\bmwezi\s+uliopita\b|\bwiki\s+iliyopita\b", re.I)
_THIS_PERIOD = re.compile(r"\bthis\s+(week|month|year)\b|\bmwezi\s+huu\b|\bwiki\s+hii\b", re.I)
_SINCE_MONTH = re.compile(rf"\bsince\s+({_MONTH_NAMES})\b", re.I)
_TODAY = re.compile(r"\b(today|leo)\b", re.I)
_YESTERDAY = re.compile(r"\b(yesterday|jana)\b", re.I)
_EXPLICIT_RE = re.compile(_EXPLICIT, re.I)
_MONTH_ALONE = re.compile(rf"\b(?:in|for|of|month of|mwezi wa)\s+({_MONTH_NAMES})\b(?:\s+(\d{{4}}))?", re.I)

_MASKABLE = (_RANGE, _LAST_N, _N_AGO, _SW_MONTHS, _EXPLICIT_RE, _MONTH_ALONE)


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


def add_months(day: date, months: int) -> date:
    """`day` moved by `months` (negative = back), clamped to the end of the target month."""
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _month_bounds(year: int, month: int) -> DateRange:
    return DateRange(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))


def _count(token: str) -> int:
    token = token.lower()
    return WORD_NUMBERS[token] if token in WORD_NUMBERS else int(token)


def _expand_year(year: int) -> int:
    return year + 2000 if year < 100 else year


def parse_explicit_date(text: str, today: date) -> date | None:
    """One explicit date: 2026-03-05, 5/3/2026 (day first, Kenyan style), 5th March, March 5 2026."""
    text = text.strip().lower()
    try:
        if re.fullmatch(_ISO, text):
            year, month, day = (int(p) for p in text.split("-"))
            return date(year, month, day)
        if re.fullmatch(_DMY, text):
            day, month, year = (int(p) for p in re.split(r"[/.-]", text))
            return date(_expand_year(year), month, day)
        day_match = re.search(r"\d{1,2}(?=(?:st|nd|rd|th)?\b(?!\d))", text)
        month_match = re.search(_MONTH_NAMES, text)
        year_match = re.search(r"\b(\d{4})\b", text)
        if day_match and month_match:
            month = MONTHS[month_match.group(0)]
            year = int(year_match.group(1)) if year_match else today.year
            candidate = date(year, month, int(day_match.group(0)))
            # "5th March" with no year means the most recent one, not a future date.
            if not year_match and candidate > today:
                candidate = date(year - 1, month, candidate.day)
            return candidate
    except ValueError:
        return None
    return None


def _relative_range(text: str, today: date) -> DateRange | None:
    if match := _LAST_N.search(text):
        count, unit = _count(match.group(1)), match.group(2).lower()
        if unit == "month":
            return DateRange(add_months(today, -count), today)
        if unit == "year":
            return DateRange(add_months(today, -12 * count), today)
        return DateRange(today - timedelta(days=count * UNIT_DAYS[unit]), today)
    if match := _N_AGO.search(text):
        count, unit = _count(match.group(1)), match.group(2).lower()
        day = add_months(today, -count) if unit == "month" else today - timedelta(days=count * UNIT_DAYS[unit])
        return DateRange(day, day)
    if match := _SW_MONTHS.search(text):
        return DateRange(add_months(today, -SWAHILI_MONTH_COUNTS[match.group(1).lower()]), today)
    return None


def _calendar_range(text: str, today: date) -> DateRange | None:
    if match := _LAST_PERIOD.search(text):
        unit = (match.group(1) or ("month" if "mwezi" in match.group(0).lower() else "week")).lower()
        if unit == "month":
            previous = add_months(today, -1)
            return _month_bounds(previous.year, previous.month)
        if unit == "year":
            return DateRange(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31))
        return DateRange(today - timedelta(days=7), today)
    if match := _THIS_PERIOD.search(text):
        unit = (match.group(1) or ("month" if "mwezi" in match.group(0).lower() else "week")).lower()
        if unit == "month":
            return DateRange(today.replace(day=1), today)
        if unit == "year":
            return DateRange(date(today.year, 1, 1), today)
        return DateRange(today - timedelta(days=today.weekday()), today)
    if match := _SINCE_MONTH.search(text):
        month = MONTHS[match.group(1).lower()]
        year = today.year if month <= today.month else today.year - 1
        return DateRange(date(year, month, 1), today)
    if match := _MONTH_ALONE.search(text):
        month = MONTHS[match.group(1).lower()]
        year = int(match.group(2)) if match.group(2) else (today.year if month <= today.month else today.year - 1)
        return _month_bounds(year, month)
    return None


def _single_day(text: str, today: date) -> DateRange | None:
    if _TODAY.search(text):
        return DateRange(today, today)
    if _YESTERDAY.search(text):
        yesterday = today - timedelta(days=1)
        return DateRange(yesterday, yesterday)
    if match := _EXPLICIT_RE.search(text):
        day = parse_explicit_date(match.group(0), today)
        if day:
            return DateRange(day, day)
    return None


def parse_date_range(text: str, today: date) -> DateRange | None:
    """The period a message talks about, or None. End is inclusive."""
    if match := _RANGE.search(text):
        start = parse_explicit_date(match.group(1), today)
        end = parse_explicit_date(match.group(2), today)
        if start and end:
            return DateRange(min(start, end), max(start, end))
    return _relative_range(text, today) or _calendar_range(text, today) or _single_day(text, today)


def mask_dates(text: str, placeholder: str = " ") -> str:
    """Blank out date phrases so their digits are not read as amounts."""
    for pattern in _MASKABLE:
        text = pattern.sub(lambda m: placeholder * len(m.group(0)), text)
    return text
