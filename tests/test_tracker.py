from __future__ import annotations

import pandas as pd

from src.alerts.tracker import TradeTracker
from src.strategy.types import SignalEvent
from tests.helpers import make_df


def _event(ts: str = "2026-11-10 12:00") -> SignalEvent:
    return SignalEvent(
        symbol="XAUUSD",
        setup="A",
        side="long",
        tf="15m",
        entry=100.0,
        sl=95.0,
        tp1=110.0,
        tp2=115.0,
        rr=2.0,
        confidence=80,
        reasons=["test"],
        session="overlap",
        regime="RANGING",
        trigger_ts=pd.Timestamp(ts, tz="UTC"),
    )


def _frame(closes, highs, lows, start="2026-11-10 12:15"):
    return make_df(closes, highs=highs, lows=lows, start=start)


def test_tp1_update_and_single_shot(tmp_path):
    tracker = TradeTracker(tmp_path / "signals.db")
    event = _event()
    assert tracker.open_signal(event) is True
    assert tracker.open_signal(event) is False

    df = _frame([101, 108, 111], [102, 109, 112], [100, 107, 110])
    updates = tracker.evaluate(df, now=df.index[-1], commit=True)
    assert len(updates) == 1
    update = updates[0]
    assert update.status == "TP1"
    assert update.exit_price == 110.0
    assert abs(update.result_r - 2.0) < 1e-9

    assert tracker.evaluate(df, now=df.index[-1], commit=True) == []
    tracker.close()


def test_sl_priority_when_bar_hits_both(tmp_path):
    tracker = TradeTracker(tmp_path / "signals.db")
    tracker.open_signal(_event())
    df = _frame([100.5], [111.0], [94.0])
    updates = tracker.evaluate(df, now=df.index[-1], commit=True)
    assert len(updates) == 1
    assert updates[0].status == "SL"
    assert updates[0].result_r == -1.0
    tracker.close()


def test_expired_after_max_hold(tmp_path):
    tracker = TradeTracker(tmp_path / "signals.db")
    tracker.open_signal(_event())
    df = _frame([100.2, 100.4, 100.6], [100.5, 100.7, 100.9], [99.9, 100.1, 100.3])
    now = df.index[-1] + pd.Timedelta(minutes=5)
    updates = tracker.evaluate(df, now=now, max_hold_minutes=30, commit=True)
    assert len(updates) == 1
    assert updates[0].status == "EXPIRED"
    assert abs(updates[0].result_r - 0.12) < 1e-9
    tracker.close()


def test_no_update_while_open(tmp_path):
    tracker = TradeTracker(tmp_path / "signals.db")
    tracker.open_signal(_event())
    df = _frame([100.2], [100.5], [99.9])
    assert tracker.evaluate(df, now=df.index[-1], commit=True) == []
    tracker.close()
