from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7), "WIB")

SESSION_LABELS = {
    "asia": "Asia",
    "london_open": "London open",
    "london_mid": "London",
    "overlap": "LDN/NY overlap",
    "ny_open": "NY open",
    "ny": "New York",
    "break": "Daily break",
}

SESSION_SCORES = {
    "overlap": 3,
    "london_open": 2,
    "ny_open": 2,
    "london_mid": 1,
    "ny": 1,
    "asia": 0,
    "break": 0,
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_wib(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(WIB)


def to_wib_str(dt: datetime, fmt: str = "%d %b %Y %H:%M WIB") -> str:
    return to_wib(dt).strftime(fmt)


def session_label(dt: datetime) -> str:
    """Session label in UTC, matching docs/02-spesifikasi-strategi.md §13.4."""
    hour = ensure_utc(dt).hour
    if hour < 7:
        return "asia"
    if hour < 10:
        return "london_open"
    if hour < 12:
        return "london_mid"
    if hour < 15:
        return "overlap"
    if hour < 16:
        return "ny_open"
    if hour < 21:
        return "ny"
    return "break"


def session_score(label: str) -> int:
    return SESSION_SCORES.get(label, 0)


def session_display(label: str) -> str:
    return SESSION_LABELS.get(label, label)


def in_killzone(dt: datetime) -> bool:
    return session_label(dt) in {"london_open", "overlap", "ny_open"}


def is_break(dt: datetime) -> bool:
    return session_label(dt) == "break"


def is_market_open(dt: datetime) -> bool:
    ts = ensure_utc(dt)
    weekday = ts.weekday()
    if weekday == 5:
        return False
    if weekday == 6 and ts.hour < 22:
        return False
    if weekday == 4 and ts.hour >= 21:
        return False
    return True


def within_window(dt: datetime, start: str, end: str) -> bool:
    ts = ensure_utc(dt)
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    now_m = ts.hour * 60 + ts.minute
    if start_m <= end_m:
        return start_m <= now_m < end_m
    return now_m >= start_m or now_m < end_m
