from __future__ import annotations

from src.strategy.structure import confirmation_after_sweep
from tests.helpers import make_df


def test_confirmation_after_sweep_long():
    df = make_df([9.5, 9.8, 11.0], highs=[10.0, 10.0, 11.2], lows=[9.0, 9.4, 9.9])
    assert confirmation_after_sweep(df, 0, "long", atr_value=1.0, displacement_mult=1.0) is True


def test_confirmation_after_sweep_long_fails_without_breakout():
    df = make_df([9.5, 9.8, 9.9], highs=[10.0, 10.0, 10.0], lows=[9.0, 9.4, 9.7])
    assert confirmation_after_sweep(df, 0, "long", atr_value=1.0, displacement_mult=1.0) is False


def test_confirmation_after_sweep_short():
    df = make_df([10.5, 10.2, 9.0], highs=[11.0, 10.6, 9.6], lows=[10.0, 9.8, 8.8])
    assert confirmation_after_sweep(df, 0, "short", atr_value=1.0, displacement_mult=1.0) is True
