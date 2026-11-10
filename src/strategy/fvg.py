from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class FVG:
    side: str
    low: float
    high: float
    index: int
    ts: object = None
    filled_pct: float = 0.0

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0

    @property
    def size(self) -> float:
        return self.high - self.low


def _fill_fraction(df: pd.DataFrame, fvg: FVG) -> float:
    size = fvg.size
    if size <= 0:
        return 1.0
    after = df.iloc[fvg.index + 1 :]
    if after.empty:
        return 0.0
    if fvg.side == "long":
        deepest = float(after["low"].min())
        filled = (fvg.high - deepest) / size
    else:
        highest = float(after["high"].max())
        filled = (highest - fvg.low) / size
    return max(0.0, min(1.0, filled))


def find_fvgs(
    df: pd.DataFrame,
    atr_series: pd.Series,
    min_atr_mult: float = 0.15,
    lookback: int = 60,
) -> list[FVG]:
    results: list[FVG] = []
    start = max(2, len(df) - lookback)
    for i in range(start, len(df)):
        atr_value = float(atr_series.iloc[i])
        if atr_value <= 0:
            continue
        min_size = atr_value * min_atr_mult

        gap_low = float(df["high"].iloc[i - 2])
        gap_high = float(df["low"].iloc[i])
        if gap_high - gap_low >= min_size:
            fvg = FVG("long", gap_low, gap_high, i, df.index[i])
            fvg.filled_pct = _fill_fraction(df, fvg)
            results.append(fvg)
            continue

        bear_low = float(df["low"].iloc[i - 2])
        bear_high = float(df["high"].iloc[i])
        if bear_low - bear_high >= min_size:
            fvg = FVG("short", bear_high, bear_low, i, df.index[i])
            fvg.filled_pct = _fill_fraction(df, fvg)
            results.append(fvg)
    return results


def select_fvg(
    fvgs: list[FVG], side: str, price: float, max_fill: float = 0.5
) -> FVG | None:
    candidates = [
        f
        for f in fvgs
        if f.side == side and f.filled_pct <= max_fill and f.low <= price <= f.high
    ]
    if not candidates:
        candidates = [f for f in fvgs if f.side == side and f.filled_pct <= max_fill]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.index)
