from __future__ import annotations

from src.strategy.liquidity import cluster_levels, find_sweep
from tests.helpers import make_df


def test_cluster_groups_equal_prices():
    levels = cluster_levels([100.0, 100.1, 105.0], tolerance=0.3, kind="bsl", min_count=2)
    assert len(levels) == 1
    assert abs(levels[0].price - 100.05) < 1e-9
    assert levels[0].count == 2


def test_sweep_detected_on_last_bar():
    df = make_df([101, 101, 101], highs=[102, 102, 102], lows=[99, 99, 98])
    idx = find_sweep(df, level=100.0, side="long", atr_value=4.0, pierce_mult=0.05, lookback=3)
    assert idx == 2


def test_no_sweep_without_close_reclaim():
    df = make_df([98, 98, 97], highs=[99, 99, 99], lows=[96, 96, 95])
    idx = find_sweep(df, level=100.0, side="long", atr_value=4.0, pierce_mult=0.05, lookback=3)
    assert idx is None
