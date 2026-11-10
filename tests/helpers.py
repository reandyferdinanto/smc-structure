from __future__ import annotations

import pandas as pd


def make_df(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    freq: str = "15min",
    start: str = "2026-11-03 00:00",
) -> pd.DataFrame:
    index = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC")
    close = pd.Series(closes, index=index, dtype=float)
    high = pd.Series(highs, index=index, dtype=float) if highs is not None else close + 1.0
    low = pd.Series(lows, index=index, dtype=float) if lows is not None else close - 1.0
    open_ = close.shift(1).fillna(close)
    volume = pd.Series(100.0, index=index)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )
