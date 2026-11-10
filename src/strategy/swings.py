from __future__ import annotations

import numpy as np
import pandas as pd


def pivot_indices(df: pd.DataFrame, k: int = 3) -> tuple[list[int], list[int]]:
    """Confirmed fractal pivots with strict comparisons on both sides."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    pivot_highs: list[int] = []
    pivot_lows: list[int] = []
    n = len(df)
    for i in range(k, n - k):
        window_h = highs[i - k : i + k + 1]
        window_l = lows[i - k : i + k + 1]
        if highs[i] == window_h.max() and np.sum(window_h == highs[i]) == 1:
            pivot_highs.append(i)
        if lows[i] == window_l.min() and np.sum(window_l == lows[i]) == 1:
            pivot_lows.append(i)
    return pivot_highs, pivot_lows


def pivot_prices(df: pd.DataFrame, k: int = 3) -> tuple[list[float], list[float]]:
    hi_idx, lo_idx = pivot_indices(df, k)
    return (
        [float(df["high"].iloc[i]) for i in hi_idx],
        [float(df["low"].iloc[i]) for i in lo_idx],
    )


def last_swing(df: pd.DataFrame, k: int = 3) -> tuple[float | None, float | None]:
    highs, lows = pivot_prices(df, k)
    return (highs[-1] if highs else None, lows[-1] if lows else None)


def trend_from_pivots(highs: list[float], lows: list[float]) -> int:
    if len(highs) < 2 or len(lows) < 2:
        return 0
    higher_high = highs[-1] > highs[-2]
    higher_low = lows[-1] > lows[-2]
    lower_high = highs[-1] < highs[-2]
    lower_low = lows[-1] < lows[-2]
    if higher_high and higher_low:
        return 1
    if lower_high and lower_low:
        return -1
    return 0
