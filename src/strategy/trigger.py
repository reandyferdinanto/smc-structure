from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .bollinger import atr


@dataclass
class ArmedSetup:
    key: str
    symbol: str
    setup: str
    side: str
    zone_low: float
    zone_high: float
    sl: float
    tp1: float
    tp2: float
    confidence: int = 0
    session: str = ""
    regime: str = ""


@dataclass
class TriggerResult:
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr: float
    reasons: list[str] = field(default_factory=list)


def confirm(
    df: pd.DataFrame,
    armed: ArmedSetup,
    atr_value: float,
    zone_tol_mult: float = 0.10,
    min_body_mult: float = 0.40,
    max_chase_mult: float = 0.15,
    sweep_lookback: int = 6,
    min_rr: float = 1.2,
) -> TriggerResult | None:
    """Lower-TF entry trigger: price in zone + micro sweep + micro BOS + body."""
    if len(df) < sweep_lookback + 2 or atr_value <= 0:
        return None

    last = df.iloc[-1]
    close = float(last["close"])
    open_price = float(last["open"])
    high = float(last["high"])
    low = float(last["low"])
    body = abs(close - open_price)
    tolerance = atr_value * zone_tol_mult

    if armed.side == "long":
        if not (armed.zone_low - tolerance <= close <= armed.zone_high + tolerance):
            return None
        if close > armed.zone_high + atr_value * max_chase_mult:
            return None
        if close <= open_price or body < atr_value * min_body_mult:
            return None
        prior_low = float(df["low"].iloc[-sweep_lookback:-1].min())
        prior_high = float(df["high"].iloc[-2])
        micro_sweep = low <= prior_low and close > prior_low
        micro_bos = close > prior_high
        if not (micro_sweep and micro_bos):
            return None
        entry = close
        sl = min(armed.sl, low - 0.10 * atr_value)
        risk = entry - sl
        if risk <= 0:
            return None
        rr = (armed.tp1 - entry) / risk
        reasons = ["zone_touch", "micro_sweep", "micro_bos"]
    else:
        if not (armed.zone_low - tolerance <= close <= armed.zone_high + tolerance):
            return None
        if close < armed.zone_low - atr_value * max_chase_mult:
            return None
        if close >= open_price or body < atr_value * min_body_mult:
            return None
        prior_high = float(df["high"].iloc[-sweep_lookback:-1].max())
        prior_low = float(df["low"].iloc[-2])
        micro_sweep = high >= prior_high and close < prior_high
        micro_bos = close < prior_low
        if not (micro_sweep and micro_bos):
            return None
        entry = close
        sl = max(armed.sl, high + 0.10 * atr_value)
        risk = sl - entry
        if risk <= 0:
            return None
        rr = (entry - armed.tp1) / risk
        reasons = ["zone_touch", "micro_sweep", "micro_bos"]

    if rr < min_rr:
        return None

    return TriggerResult(
        entry=entry,
        sl=sl,
        tp1=armed.tp1,
        tp2=armed.tp2,
        rr=rr,
        reasons=reasons,
    )


def invalidated(df: pd.DataFrame, armed: ArmedSetup) -> bool:
    if df.empty:
        return False
    close = float(df["close"].iloc[-1])
    if armed.side == "long":
        return close < armed.sl
    return close > armed.sl


def atr_now(df: pd.DataFrame, length: int = 14) -> float:
    if len(df) < length + 2:
        return 0.0
    return float(atr(df, length).iloc[-1])
