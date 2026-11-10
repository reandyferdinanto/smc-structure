from __future__ import annotations

from src.macro.bias import label_for, score_from_inputs


def test_bullish_score():
    report = score_from_inputs(
        real_yield_delta_5d=-0.10,
        dxy_return_5d=-0.8,
        fed_score=0.5,
        gdelt_tone=-1.5,
        cb_score=1.0,
    )
    assert report.score >= 20
    assert report.label in {"BULLISH", "BULLISH_STRONG"}


def test_bearish_score():
    report = score_from_inputs(
        real_yield_delta_5d=0.12,
        dxy_return_5d=1.1,
        fed_score=-0.5,
        gdelt_tone=1.0,
        cb_score=-0.5,
    )
    assert report.score <= -20
    assert report.label in {"BEARISH", "BEARISH_STRONG"}


def test_neutral_labels():
    assert label_for(0) == "NEUTRAL"
    assert label_for(19) == "NEUTRAL"
    assert label_for(50) == "BULLISH_STRONG"
    assert label_for(-50) == "BEARISH_STRONG"
