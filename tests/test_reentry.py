from __future__ import annotations

from src.strategy.reentry import evaluate
from tests.helpers import make_df


def _uptrend_frame(last_open=105.0, last_high=106.0, last_low=103.8, last_close=105.5):
    closes = [100 + 0.2 * i for i in range(29)] + [last_close]
    df = make_df(
        closes,
        highs=[c + 0.5 for c in closes],
        lows=[c - 0.5 for c in closes],
    )
    row = df.index[-1]
    df.loc[row, "open"] = last_open
    df.loc[row, "high"] = last_high
    df.loc[row, "low"] = last_low
    df.loc[row, "close"] = last_close
    return df


def test_long_reentry_valid_on_bb_mid_bounce():
    df = _uptrend_frame()
    result = evaluate(
        df, "long", zone_low=104.0, zone_high=104.5, tp1=109.0, tp2=113.0, atr_value=1.0
    )
    assert result.valid is True
    assert result.reason == "valid"
    assert result.rr >= 1.2


def test_long_reentry_too_late():
    df = _uptrend_frame(last_open=106.5, last_high=108.0, last_low=106.0, last_close=107.8)
    result = evaluate(
        df, "long", zone_low=104.0, zone_high=104.5, tp1=108.0, tp2=112.0, atr_value=1.0
    )
    assert result.valid is False
    assert result.reason == "too_late"


def test_long_reentry_rr_too_low():
    df = _uptrend_frame()
    result = evaluate(
        df, "long", zone_low=104.0, zone_high=104.5, tp1=107.0, tp2=109.0, atr_value=1.0
    )
    assert result.valid is False
    assert result.reason == "rr_too_low"


def test_long_reentry_without_mid_touch():
    df = _uptrend_frame(last_low=105.2)
    result = evaluate(
        df, "long", zone_low=104.0, zone_high=104.5, tp1=108.0, tp2=112.0, atr_value=1.0
    )
    assert result.valid is False
    assert result.reason == "no_bb_mid_bounce"


def test_short_reentry_valid():
    closes = [110 - 0.2 * i for i in range(29)] + [104.5]
    df = make_df(
        closes,
        highs=[c + 0.5 for c in closes],
        lows=[c - 0.5 for c in closes],
    )
    row = df.index[-1]
    df.loc[row, "open"] = 105.0
    df.loc[row, "high"] = 106.2
    df.loc[row, "low"] = 104.2
    df.loc[row, "close"] = 104.5
    result = evaluate(
        df, "short", zone_low=105.5, zone_high=106.0, tp1=101.0, tp2=99.0, atr_value=1.0
    )
    assert result.valid is True
    assert result.reason == "valid"
