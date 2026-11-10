from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.macro.calendar import CalendarEvent, next_high_impact

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def _event(minutes_ahead: int, currency: str = "USD", impact: str = "High") -> CalendarEvent:
    return CalendarEvent(
        title="CPI y/y",
        currency=currency,
        impact=impact,
        ts_utc=NOW + timedelta(minutes=minutes_ahead),
    )


def test_next_high_impact_found():
    events = [_event(10), _event(45)]
    found = next_high_impact(events, NOW, minutes=15)
    assert found is not None
    assert found.ts_utc == NOW + timedelta(minutes=10)


def test_next_high_impact_outside_window():
    assert next_high_impact([_event(20)], NOW, minutes=15) is None


def test_next_high_impact_filters_currency_and_impact():
    assert next_high_impact([_event(5, currency="EUR")], NOW) is None
    assert next_high_impact([_event(5, impact="Medium")], NOW) is None
