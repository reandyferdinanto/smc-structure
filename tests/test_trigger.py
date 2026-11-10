from __future__ import annotations

import pandas as pd

from src.strategy.trigger import ArmedSetup, confirm, invalidated
from tests.helpers import make_df


def _armed(side: str = "long") -> ArmedSetup:
    if side == "long":
        return ArmedSetup(
            key="k", symbol="XAUUSD", setup="A", side="long",
            zone_low=100.0, zone_high=102.0, sl=97.0, tp1=108.0, tp2=112.0,
        )
    return ArmedSetup(
        key="k", symbol="XAUUSD", setup="A", side="short",
        zone_low=100.0, zone_high=102.0, sl=105.0, tp1=94.0, tp2=90.0,
    )


def test_long_trigger_confirms():
    closes = [101.0, 101.2, 100.8, 100.5, 100.9, 101.0, 101.2, 101.8]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    lows[-1] = 100.1
    df = make_df(closes, highs=highs, lows=lows)
    result = confirm(df, _armed("long"), atr_value=0.5, min_rr=1.0)
    assert result is not None
    assert result.entry == 101.8
    assert result.rr > 1.0


def test_long_trigger_rejects_chase():
    closes = [101.0, 101.2, 100.8, 100.5, 100.9, 101.0, 101.2, 105.0]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    df = make_df(closes, highs=highs, lows=lows)
    assert confirm(df, _armed("long"), atr_value=0.5) is None


def test_long_trigger_requires_bullish_body():
    closes = [101.0, 101.2, 100.8, 100.5, 100.9, 101.0, 101.2, 101.4]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.8 for c in closes]
    df = make_df(closes, highs=highs, lows=lows)
    df.iloc[-1, df.columns.get_loc("open")] = 101.5
    assert confirm(df, _armed("long"), atr_value=0.5) is None


def test_short_trigger_confirms():
    closes = [101.0, 100.9, 101.2, 101.4, 101.1, 101.0, 100.9, 100.4]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    highs[-1] = 101.8
    df = make_df(closes, highs=highs, lows=lows)
    result = confirm(df, _armed("short"), atr_value=0.5, min_rr=1.0)
    assert result is not None
    assert result.entry == 100.4


def test_invalidated_levels():
    df = make_df([96.5], highs=[97.0], lows=[96.0])
    assert invalidated(df, _armed("long")) is True
    df2 = make_df([106.0], highs=[106.5], lows=[105.5])
    assert invalidated(df2, _armed("short")) is True
