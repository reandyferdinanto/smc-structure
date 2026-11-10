from __future__ import annotations

from datetime import datetime, timezone

from src.utils.time import (
    fmt_wib_utc,
    in_killzone,
    is_break,
    is_market_open,
    session_label,
)


def _ts(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 10, hour, minute, tzinfo=timezone.utc)


def test_session_labels():
    assert session_label(_ts(2)) == "asia"
    assert session_label(_ts(8)) == "london_open"
    assert session_label(_ts(11)) == "london_mid"
    assert session_label(_ts(13)) == "overlap"
    assert session_label(_ts(15, 30)) == "ny_open"
    assert session_label(_ts(18)) == "ny"
    assert session_label(_ts(21, 30)) == "break"


def test_killzone_and_break():
    assert in_killzone(_ts(8)) is True
    assert in_killzone(_ts(13)) is True
    assert in_killzone(_ts(2)) is False
    assert is_break(_ts(21, 15)) is True


def test_fmt_wib_utc():
    assert fmt_wib_utc(_ts(4, 38), "%H:%M") == "11:38 WIB (04:38 UTC)"
    assert fmt_wib_utc(_ts(21, 5), "%H:%M") == "04:05 WIB (21:05 UTC)"


def test_market_open_weekend():
    friday_late = datetime(2026, 11, 13, 22, tzinfo=timezone.utc)
    saturday = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
    monday = datetime(2026, 11, 16, 1, tzinfo=timezone.utc)
    assert is_market_open(friday_late) is False
    assert is_market_open(saturday) is False
    assert is_market_open(monday) is True
