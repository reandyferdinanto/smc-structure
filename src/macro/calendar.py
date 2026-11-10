from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from ..utils.log import get_logger

log = get_logger("macro.calendar")

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    currency: str
    impact: str
    ts_utc: datetime
    forecast: str = ""
    previous: str = ""


def fetch_events(timeout: float = 15.0) -> list[CalendarEvent]:
    response = httpx.get(FF_URL, timeout=timeout)
    response.raise_for_status()
    events: list[CalendarEvent] = []
    for item in response.json():
        try:
            ts = datetime.fromisoformat(str(item["date"])).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        events.append(
            CalendarEvent(
                title=str(item.get("title", "")),
                currency=str(item.get("country", "")),
                impact=str(item.get("impact", "")),
                ts_utc=ts,
                forecast=str(item.get("forecast", "")),
                previous=str(item.get("previous", "")),
            )
        )
    return events


def blackout(
    events: list[CalendarEvent],
    ts: datetime,
    minutes: int = 30,
    currencies: tuple[str, ...] = ("USD",),
    impacts: tuple[str, ...] = ("High",),
) -> tuple[bool, CalendarEvent | None]:
    ts_utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    window = timedelta(minutes=minutes)
    for event in events:
        if event.currency not in currencies or event.impact not in impacts:
            continue
        if abs(event.ts_utc - ts_utc) <= window:
            return True, event
    return False, None
