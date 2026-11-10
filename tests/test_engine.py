from __future__ import annotations

import pandas as pd

from src.strategy.engine import Engine
from src.strategy.orb import build_session_range
from tests.helpers import make_df


def test_macro_conflict_rules():
    assert Engine._macro_conflict("long", -50) is True
    assert Engine._macro_conflict("short", 50) is True
    assert Engine._macro_conflict("long", 50) is False
    assert Engine._macro_conflict("short", -10) is False


def test_confidence_within_bounds():
    engine = Engine()
    from src.strategy.regime import Regime

    score = engine._confidence(
        bias=3, regime=Regime.RANGING, session="overlap", fvg=None, ob=None, macro_bias=None
    )
    assert 0 <= score <= 100


def test_build_session_range():
    index = pd.date_range("2026-11-03 07:00", periods=4, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0, 10.0],
            "high": [10.0, 11.0, 12.0, 13.0],
            "low": [5.0, 4.0, 3.0, 2.0],
            "close": [9.0, 10.0, 11.0, 12.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        },
        index=index,
    )
    rng = build_session_range(frame, "07:00", "08:00", "london", min_candles=3)
    assert rng is not None
    assert rng.high == 13.0
    assert rng.low == 2.0
    assert rng.candles == 4


def test_engine_evaluate_returns_none_on_short_data():
    engine = Engine()
    df = make_df([100.0] * 30)
    assert engine.evaluate(df, df, df) is None
