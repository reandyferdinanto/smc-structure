from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Spike:
    detected: bool
    range_ratio: float
    body_ratio: float
    direction: str


def detect_spike(
    df: pd.DataFrame,
    lookback: int = 14,
    range_mult: float = 3.0,
    body_mult: float = 2.5,
) -> Spike:
    """Detect abnormal 1m candle vs median of recent bars (unscheduled news proxy)."""
    if len(df) < lookback + 2:
        return Spike(False, 0.0, 0.0, "")

    recent = df.iloc[-lookback - 1 : -1]
    ranges = (recent["high"] - recent["low"]).astype(float)
    median = float(ranges.median())
    if median <= 0:
        return Spike(False, 0.0, 0.0, "")

    last = df.iloc[-1]
    last_range = float(last["high"] - last["low"])
    last_body = abs(float(last["close"]) - float(last["open"]))
    range_ratio = last_range / median
    body_ratio = last_body / median
    direction = "up" if float(last["close"]) > float(last["open"]) else "down"
    detected = range_ratio >= range_mult or body_ratio >= body_mult
    return Spike(detected, range_ratio, body_ratio, direction)
