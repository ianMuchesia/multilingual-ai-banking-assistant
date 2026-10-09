"""Time helpers. Everything is stored in UTC; SQLite hands datetimes back naive, so normalise."""

from datetime import date, datetime, time, timezone, tzinfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Attach UTC to a naive datetime (SQLite), or convert an aware one to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_today(tz: tzinfo) -> date:
    return utc_now().astimezone(tz).date()


def start_of_local_day(day: date, tz: tzinfo) -> datetime:
    """Midnight of `day` in the bank's timezone, as a UTC datetime."""
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
