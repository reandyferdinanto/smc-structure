from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from ..config import Config
from ..strategy.engine import Engine


@dataclass
class Trade:
    entry_ts: datetime
    exit_ts: datetime
    setup: str
    side: str
    entry: float
    sl: float
    tp1: float
    confidence: int
    r_multiple: float
    exit_reason: str


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    aggregated = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return aggregated.dropna()


def _simulate(
    df: pd.DataFrame,
    entry_index: int,
    side: str,
    sl: float,
    tp1: float,
    spread: float,
    max_hold: int,
) -> tuple[float, str, int] | None:
    if entry_index >= len(df):
        return None
    half_spread = spread / 2.0
    open_price = float(df["open"].iloc[entry_index])
    entry = open_price + half_spread if side == "long" else open_price - half_spread

    if side == "long":
        risk = entry - sl
        if risk <= 0:
            return None
        reward = tp1 - entry
        rr = reward / risk
        if rr <= 0:
            return None
        for j in range(entry_index, min(entry_index + max_hold, len(df))):
            bar = df.iloc[j]
            if float(bar["low"]) <= sl:
                return -1.0, "sl", j
            if float(bar["high"]) >= tp1:
                return rr, "tp1", j
        last = float(df["close"].iloc[min(entry_index + max_hold, len(df)) - 1])
        return (last - entry) / risk, "timeout", min(entry_index + max_hold, len(df)) - 1

    risk = sl - entry
    if risk <= 0:
        return None
    reward = entry - tp1
    rr = reward / risk
    if rr <= 0:
        return None
    for j in range(entry_index, min(entry_index + max_hold, len(df))):
        bar = df.iloc[j]
        if float(bar["high"]) >= sl:
            return -1.0, "sl", j
        if float(bar["low"]) <= tp1:
            return rr, "tp1", j
    last = float(df["close"].iloc[min(entry_index + max_hold, len(df)) - 1])
    return (entry - last) / risk, "timeout", min(entry_index + max_hold, len(df)) - 1


def run_backtest(
    df15: pd.DataFrame,
    config: Config | None = None,
    window: int = 600,
    every: int = 4,
    max_hold: int = 96,
    spread: float = 0.35,
    min_rr: float = 1.0,
) -> list[Trade]:
    """Replay M15 bars through the live engine. `every` skips bars for speed."""
    frame = df15.sort_index()
    h1 = resample_ohlcv(frame, "1h")
    h4 = resample_ohlcv(frame, "4h")
    engine = Engine(config)
    trades: list[Trade] = []

    start = max(window, 100)
    for i in range(start, len(frame) - 1, every):
        now = frame.index[i]
        w15 = frame.iloc[i - window + 1 : i + 1]
        w1 = h1.loc[:now].tail(window)
        w4 = h4.loc[:now].tail(window)
        if len(w1) < 60 or len(w4) < 60:
            continue

        signal = engine.evaluate(w15, w1, w4, now=now)
        if signal is None:
            continue

        outcome = _simulate(
            frame, i + 1, signal.side, signal.sl, signal.tp1, spread, max_hold
        )
        if outcome is None:
            continue
        r_multiple, reason, exit_index = outcome
        if reason == "tp1" and r_multiple < min_rr:
            continue

        trades.append(
            Trade(
                entry_ts=frame.index[i + 1].to_pydatetime(),
                exit_ts=frame.index[exit_index].to_pydatetime(),
                setup=signal.setup,
                side=signal.side,
                entry=float(frame["open"].iloc[i + 1]),
                sl=signal.sl,
                tp1=signal.tp1,
                confidence=signal.confidence,
                r_multiple=float(r_multiple),
                exit_reason=reason,
            )
        )
    return trades
