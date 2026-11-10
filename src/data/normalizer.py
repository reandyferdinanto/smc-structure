from __future__ import annotations

import pandas as pd

from .base import DataError, OHLCV_COLUMNS


def validate_ohlcv(df: pd.DataFrame, min_bars: int = 30) -> pd.DataFrame:
    if df is None or df.empty:
        raise DataError("empty dataframe")
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"missing columns: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataError("index is not a DatetimeIndex")
    if df.index.tz is None:
        raise DataError("index is not timezone-aware")
    if len(df) < min_bars:
        raise DataError(f"not enough bars: {len(df)} < {min_bars}")

    frame = df[OHLCV_COLUMNS].astype(float).sort_index()
    if frame.index.duplicated().any():
        raise DataError("duplicate timestamps")
    if not frame["close"].between(200, 20000).all():
        raise DataError("close outside plausible gold range")
    if (frame["high"] < frame[["open", "close"]].max(axis=1)).any():
        raise DataError("high < max(open, close)")
    if (frame["low"] > frame[["open", "close"]].min(axis=1)).any():
        raise DataError("low > min(open, close)")
    return frame
