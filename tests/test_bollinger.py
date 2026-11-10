from __future__ import annotations

import numpy as np
import pandas as pd

from src.strategy.bollinger import add_bollinger, atr, percentile_rank
from tests.helpers import make_df


def test_flat_series_has_zero_width():
    df = make_df([100.0] * 40)
    bb = add_bollinger(df, 20, 2.0)
    assert bb["bb_width"].iloc[-1] == 0.0
    assert bb["bb_up"].iloc[-1] == bb["bb_lo"].iloc[-1] == 100.0


def test_uptrend_pct_b_near_upper_band():
    df = make_df([100 + i for i in range(40)], highs=[100 + i + 1 for i in range(40)],
                 lows=[100 + i - 1 for i in range(40)])
    bb = add_bollinger(df, 20, 2.0)
    assert bb["pct_b"].iloc[-1] > 0.8


def test_spike_breaks_upper_band():
    closes = [100 + i for i in range(39)] + [200.0]
    df = make_df(closes, highs=[c + 1 for c in closes], lows=[c - 1 for c in closes])
    bb = add_bollinger(df, 20, 2.0)
    assert bb["pct_b"].iloc[-1] > 1.0


def test_percentile_rank_monotonic():
    series = pd.Series(np.arange(1, 51, dtype=float))
    rank = percentile_rank(series, 20)
    assert rank.iloc[-1] == 100.0


def test_atr_positive():
    df = make_df([100 + (i % 5) for i in range(40)])
    assert atr(df, 14).iloc[-1] > 0
