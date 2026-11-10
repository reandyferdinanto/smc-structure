from __future__ import annotations

from src.backtest.metrics import summarize
from src.backtest.runner import Trade


def _trade(r: float) -> Trade:
    from datetime import datetime, timezone

    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Trade(
        entry_ts=ts,
        exit_ts=ts,
        setup="A",
        side="long",
        entry=100.0,
        sl=95.0,
        tp1=110.0,
        confidence=80,
        r_multiple=r,
        exit_reason="tp1" if r > 0 else "sl",
    )


def test_summarize_known_values():
    metrics = summarize([_trade(2.0), _trade(-1.0), _trade(1.0), _trade(-1.0)])
    assert metrics.trades == 4
    assert metrics.wins == 2
    assert metrics.win_rate == 0.5
    assert abs(metrics.expectancy_r - 0.25) < 1e-9
    assert abs(metrics.profit_factor - 1.5) < 1e-9
    assert metrics.total_r == 1.0


def test_summarize_empty():
    metrics = summarize([])
    assert metrics.trades == 0
    assert metrics.expectancy_r == 0.0
