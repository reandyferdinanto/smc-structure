from __future__ import annotations

from enum import Enum

import numpy as np
import pandas as pd

from .bollinger import add_bollinger, atr, percentile_rank


class Regime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"


def adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr_value = tr.ewm(alpha=1.0 / length, adjust=False).mean()

    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / length, adjust=False).mean() / atr_value
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / length, adjust=False).mean() / atr_value
    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denominator
    return dx.ewm(alpha=1.0 / length, adjust=False).mean().fillna(0.0)


def classify(
    df: pd.DataFrame,
    adx_threshold: float = 25.0,
    atr_rank_volatile: float = 80.0,
    bbw_rank_volatile: float = 70.0,
    ema_length: int = 50,
    ema_slope_min: float = 0.5,
) -> Regime:
    if len(df) < 60:
        return Regime.RANGING

    atr_series = atr(df, 14)
    atr_rank = percentile_rank(atr_series, 100).iloc[-1]
    bb = add_bollinger(df, 20, 2.0)
    bbw_rank = percentile_rank(bb["bb_width"], 100).iloc[-1]
    adx_value = float(adx(df, 14).iloc[-1])

    ema = df["close"].ewm(span=ema_length, adjust=False).mean()
    atr_last = float(atr_series.iloc[-1]) or 1e-9
    slope = float(ema.iloc[-1] - ema.iloc[-10]) / atr_last

    if (
        not np.isnan(atr_rank)
        and not np.isnan(bbw_rank)
        and atr_rank >= atr_rank_volatile
        and bbw_rank >= bbw_rank_volatile
    ):
        return Regime.VOLATILE
    if adx_value >= adx_threshold and abs(slope) >= ema_slope_min:
        return Regime.TRENDING
    return Regime.RANGING
