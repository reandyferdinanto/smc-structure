from __future__ import annotations

import numpy as np
import pandas as pd


def add_bollinger(df: pd.DataFrame, length: int = 20, mult: float = 2.0) -> pd.DataFrame:
    out = df.copy()
    middle = out["close"].rolling(length, min_periods=length).mean()
    std = out["close"].rolling(length, min_periods=length).std(ddof=0)
    out["bb_mid"] = middle
    out["bb_up"] = middle + mult * std
    out["bb_lo"] = middle - mult * std
    out["bb_width"] = (out["bb_up"] - out["bb_lo"]) / middle * 100.0
    span = (out["bb_up"] - out["bb_lo"]).replace(0, np.nan)
    out["pct_b"] = (out["close"] - out["bb_lo"]) / span
    return out


def percentile_rank(series: pd.Series, window: int = 100) -> pd.Series:
    def rank(values: np.ndarray) -> float:
        last = values[-1]
        if np.isnan(last):
            return np.nan
        return float((values <= last).mean() * 100.0)

    return series.rolling(window, min_periods=max(10, window // 10)).apply(rank, raw=True)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def squeeze_series(
    df_bb: pd.DataFrame, lookback: int = 100, percentile: int = 25
) -> pd.Series:
    rank = percentile_rank(df_bb["bb_width"], lookback)
    return rank <= percentile


def is_squeeze(
    df_bb: pd.DataFrame, lookback: int = 100, percentile: int = 25, recent: int = 3
) -> bool:
    series = squeeze_series(df_bb, lookback, percentile)
    return bool(series.tail(recent).fillna(False).any())


def band_distance_atr(df_bb: pd.DataFrame, atr_series: pd.Series, side: str) -> float:
    if side == "long":
        return float((df_bb["close"].iloc[-1] - df_bb["bb_lo"].iloc[-1]) / atr_series.iloc[-1])
    return float((df_bb["bb_up"].iloc[-1] - df_bb["close"].iloc[-1]) / atr_series.iloc[-1])
