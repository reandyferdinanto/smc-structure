from __future__ import annotations

import pandas as pd

from src.strategy.fvg import find_fvgs
from tests.helpers import make_df


def test_bullish_fvg_detected():
    df = make_df([100, 101, 104], highs=[101, 102, 105], lows=[99, 100, 103])
    atr_series = pd.Series(5.0, index=df.index)
    fvgs = find_fvgs(df, atr_series, min_atr_mult=0.15)
    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.side == "long"
    assert fvg.low == 101.0
    assert fvg.high == 103.0
    assert fvg.filled_pct == 0.0


def test_ignores_small_gap():
    df = make_df([100, 100, 100.1], highs=[100, 100, 100.2], lows=[99.9, 99.9, 100.0])
    atr_series = pd.Series(10.0, index=df.index)
    assert find_fvgs(df, atr_series, min_atr_mult=0.15) == []
