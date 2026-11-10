from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pandas as pd


@dataclass(frozen=True)
class Level:
    price: float
    count: int
    kind: str


def cluster_levels(
    prices: Sequence[float], tolerance: float, kind: str, min_count: int = 2
) -> list[Level]:
    if not prices:
        return []
    ordered = sorted(float(p) for p in prices)
    clusters: list[list[float]] = [[ordered[0]]]
    for price in ordered[1:]:
        if abs(price - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(price)
        else:
            clusters.append([price])
    levels = [
        Level(price=sum(group) / len(group), count=len(group), kind=kind)
        for group in clusters
        if len(group) >= min_count
    ]
    return levels


def equal_levels(
    highs: Sequence[float],
    lows: Sequence[float],
    atr_value: float,
    tol_mult: float = 0.10,
    min_count: int = 2,
) -> list[Level]:
    tolerance = max(atr_value * tol_mult, 1e-9)
    levels = cluster_levels(highs, tolerance, "bsl", min_count)
    levels += cluster_levels(lows, tolerance, "ssl", min_count)
    return levels


def find_sweep(
    df: pd.DataFrame,
    level: float,
    side: str,
    atr_value: float,
    pierce_mult: float = 0.05,
    lookback: int = 3,
) -> int | None:
    """Return bar index of the most recent sweep of ``level`` for the given side."""
    pierce = max(atr_value * pierce_mult, 1e-9)
    start = max(0, len(df) - lookback)
    match: int | None = None
    for i in range(start, len(df)):
        if side == "long":
            if df["low"].iloc[i] < level - pierce and df["close"].iloc[i] > level:
                match = i
        else:
            if df["high"].iloc[i] > level + pierce and df["close"].iloc[i] < level:
                match = i
    return match


def nearest_above(prices: Sequence[float], price: float) -> float | None:
    candidates = [p for p in prices if p > price]
    return min(candidates) if candidates else None


def nearest_below(prices: Sequence[float], price: float) -> float | None:
    candidates = [p for p in prices if p < price]
    return max(candidates) if candidates else None
