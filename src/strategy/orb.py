from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class SessionRange:
    name: str
    high: float
    low: float
    candles: int
    window_end: str = ""

    @property
    def size(self) -> float:
        return self.high - self.low


def build_session_range(
    df: pd.DataFrame,
    start: str,
    end: str,
    name: str,
    min_candles: int = 3,
) -> SessionRange | None:
    if df.empty:
        return None
    latest_day = df.index[-1].date()
    day_df = df[df.index.date == latest_day]
    if day_df.empty:
        return None
    window = day_df.between_time(start, end, inclusive="left")
    if len(window) < min_candles:
        return None
    return SessionRange(
        name=name,
        high=float(window["high"].max()),
        low=float(window["low"].min()),
        candles=len(window),
        window_end=end,
    )


def breakout_side(
    df: pd.DataFrame,
    session_range: SessionRange,
    atr_value: float,
    tolerance_mult: float = 0.10,
    min_inside: int = 3,
) -> str | None:
    if df.empty or atr_value <= 0:
        return None
    latest_day = df.index[-1].date()
    day_df = df[df.index.date == latest_day]
    if day_df.empty:
        return None
    if session_range.window_end:
        day_df = day_df.between_time(session_range.window_end, "23:59")

    tolerance = atr_value * tolerance_mult
    inside_count = 0
    for _, bar in day_df.iterrows():
        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        inside = session_range.low <= close <= session_range.high
        if inside:
            inside_count += 1
            continue
        if inside_count < min_inside:
            continue
        if close > session_range.high + tolerance and high > session_range.high:
            return "long"
        if close < session_range.low - tolerance and low < session_range.low:
            return "short"
    return None
