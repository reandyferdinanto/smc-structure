from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .bollinger import add_bollinger


@dataclass
class ReentryResult:
    valid: bool
    reason: str
    side: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr: float
    touched_mid: bool = False


def evaluate(
    df: pd.DataFrame,
    side: str,
    zone_low: float,
    zone_high: float,
    tp1: float,
    tp2: float,
    atr_value: float,
    min_rr: float = 1.2,
    max_progress: float = 0.70,
    tol_mult: float = 0.15,
    min_body_mult: float = 0.30,
    swing_lookback: int = 10,
    invalid_level: float | None = None,
) -> ReentryResult:
    """Re-entry after a missed signal: pullback to BB middle, remaining RR must be good."""
    empty = ReentryResult(False, "insufficient_data", side, 0, 0, tp1, tp2, 0)
    if len(df) < 25 or atr_value <= 0:
        return empty

    bb = add_bollinger(df, 20, 2.0)
    if bb["bb_mid"].isna().iloc[-1]:
        return empty

    last = df.iloc[-1]
    close = float(last["close"])
    open_price = float(last["open"])
    high = float(last["high"])
    low = float(last["low"])
    body = abs(close - open_price)
    mid = float(bb["bb_mid"].iloc[-1])
    zone_mid = (zone_low + zone_high) / 2.0
    tolerance = atr_value * tol_mult

    if side == "long":
        if invalid_level is not None and close < invalid_level:
            return ReentryResult(False, "below_invalidation", side, close, 0, tp1, tp2, 0)
        full_move = tp1 - zone_mid
        if full_move <= 0:
            return ReentryResult(False, "invalid_target", side, close, 0, tp1, tp2, 0)
        progress = (close - zone_mid) / full_move
        if progress >= max_progress:
            return ReentryResult(False, "too_late", side, close, 0, tp1, tp2, 0)
        touched = low <= mid + tolerance
        bounced = close > mid and close > open_price
        if not touched or not bounced or body < atr_value * min_body_mult:
            return ReentryResult(False, "no_bb_mid_bounce", side, close, 0, tp1, tp2, 0)
        swing_low = float(df["low"].iloc[-swing_lookback:].min())
        sl = min(swing_low, mid) - 0.10 * atr_value
        risk = close - sl
        if risk <= 0:
            return ReentryResult(False, "invalid_stop", side, close, 0, tp1, tp2, 0)
        rr = (tp1 - close) / risk
        valid = rr >= min_rr
        return ReentryResult(
            valid,
            "valid" if valid else "rr_too_low",
            side,
            close,
            sl,
            tp1,
            tp2,
            rr,
            touched_mid=True,
        )

    if side == "short":
        if invalid_level is not None and close > invalid_level:
            return ReentryResult(False, "above_invalidation", side, close, 0, tp1, tp2, 0)
        full_move = zone_mid - tp1
        if full_move <= 0:
            return ReentryResult(False, "invalid_target", side, close, 0, tp1, tp2, 0)
        progress = (zone_mid - close) / full_move
        if progress >= max_progress:
            return ReentryResult(False, "too_late", side, close, 0, tp1, tp2, 0)
        touched = high >= mid - tolerance
        bounced = close < mid and close < open_price
        if not touched or not bounced or body < atr_value * min_body_mult:
            return ReentryResult(False, "no_bb_mid_bounce", side, close, 0, tp1, tp2, 0)
        swing_high = float(df["high"].iloc[-swing_lookback:].max())
        sl = max(swing_high, mid) + 0.10 * atr_value
        risk = sl - close
        if risk <= 0:
            return ReentryResult(False, "invalid_stop", side, close, 0, tp1, tp2, 0)
        rr = (close - tp1) / risk
        valid = rr >= min_rr
        return ReentryResult(
            valid,
            "valid" if valid else "rr_too_low",
            side,
            close,
            sl,
            tp1,
            tp2,
            rr,
            touched_mid=True,
        )

    return ReentryResult(False, "invalid_side", side, close, 0, tp1, tp2, 0)
