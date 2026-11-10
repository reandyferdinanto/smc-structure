from __future__ import annotations

from src.macro.guard import detect_spike
from tests.helpers import make_df


def test_calm_market_no_spike():
    df = make_df([100.0] * 20, highs=[100.5] * 20, lows=[99.5] * 20)
    spike = detect_spike(df)
    assert spike.detected is False


def test_range_spike_detected():
    closes = [100.0] * 19 + [104.0]
    highs = [100.5] * 19 + [106.0]
    lows = [99.5] * 19 + [99.0]
    df = make_df(closes, highs=highs, lows=lows)
    spike = detect_spike(df)
    assert spike.detected is True
    assert spike.direction == "up"
    assert spike.range_ratio >= 3.0


def test_body_spike_detected():
    closes = [100.0] * 20
    highs = [100.5] * 20
    lows = [99.5] * 20
    df = make_df(closes, highs=highs, lows=lows)
    df.iloc[-1, df.columns.get_loc("open")] = 96.0
    df.iloc[-1, df.columns.get_loc("high")] = 101.0
    df.iloc[-1, df.columns.get_loc("low")] = 95.0
    spike = detect_spike(df)
    assert spike.detected is True
    assert spike.direction == "up"


def test_short_history_is_safe():
    df = make_df([100.0, 101.0], highs=[100.5, 101.5], lows=[99.5, 100.5])
    assert detect_spike(df).detected is False
