from __future__ import annotations

from src.strategy.swings import pivot_prices, trend_from_pivots
from tests.helpers import make_df


def test_pivot_detection_basic():
    highs = [10, 11, 12, 11, 10, 11, 13, 11, 10]
    lows = [8, 7, 6, 7, 8, 7, 5, 7, 8]
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    df = make_df(closes, highs=highs, lows=lows)
    hi, lo = pivot_prices(df, k=1)
    assert hi == [12.0, 13.0]
    assert lo == [6.0, 5.0]


def test_trend_from_pivots():
    assert trend_from_pivots([10, 12], [5, 7]) == 1
    assert trend_from_pivots([12, 10], [7, 5]) == -1
    assert trend_from_pivots([12, 13], [6, 5]) == 0
