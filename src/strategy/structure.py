from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .swings import pivot_prices, trend_from_pivots


@dataclass
class StructureState:
    trend: int
    swing_high: float | None
    swing_low: float | None
    last_break: str | None = None
    body_atr: float = 0.0


def analyze(
    df: pd.DataFrame,
    k: int = 5,
    atr_value: float | None = None,
    displacement_mult: float = 1.2,
    lookback: int = 5,
) -> StructureState:
    highs, lows = pivot_prices(df, k)
    trend = trend_from_pivots(highs, lows)
    swing_high = highs[-1] if highs else None
    swing_low = lows[-1] if lows else None

    if not highs or not lows or len(df) < 3:
        return StructureState(trend=trend, swing_high=swing_high, swing_low=swing_low)

    threshold = (atr_value or 0.0) * displacement_mult
    recent = df.tail(max(lookback, 1))
    last_break: str | None = None
    body_atr = 0.0

    for i in range(len(recent) - 1, -1, -1):
        bar = recent.iloc[i]
        body = abs(float(bar["close"]) - float(bar["open"]))
        body_atr = body / atr_value if atr_value else 0.0
        if body < threshold:
            continue
        if float(bar["close"]) > swing_high:
            last_break = "bullish_bos" if trend > 0 else "bullish_choch"
            break
        if float(bar["close"]) < swing_low:
            last_break = "bearish_bos" if trend < 0 else "bearish_choch"
            break

    return StructureState(
        trend=trend,
        swing_high=swing_high,
        swing_low=swing_low,
        last_break=last_break,
        body_atr=body_atr,
    )


def has_internal_choch(
    df: pd.DataFrame,
    side: str,
    atr_value: float,
    k: int = 2,
    displacement_mult: float = 1.2,
    lookback: int = 6,
) -> bool:
    state = analyze(
        df, k=k, atr_value=atr_value, displacement_mult=displacement_mult, lookback=lookback
    )
    if side == "long":
        return state.last_break in {"bullish_choch", "bullish_bos"}
    return state.last_break in {"bearish_choch", "bearish_bos"}


def displacement_after(
    df: pd.DataFrame, start_index: int, atr_value: float, mult: float = 1.2
) -> bool:
    window = df.iloc[start_index:]
    if window.empty:
        return False
    body = (window["close"] - window["open"]).abs()
    return bool(body.max() >= atr_value * mult)
