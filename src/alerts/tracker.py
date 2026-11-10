from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..strategy.types import SignalEvent

DEFAULT_PATH = Path("state/signals.db")


@dataclass
class Update:
    key: str
    symbol: str
    setup: str
    side: str
    entry: float
    sl: float
    tp1: float
    status: str
    exit_price: float
    result_r: float
    opened_at: str


class TradeTracker:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_signals (
                dedupe_key TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                setup TEXT NOT NULL,
                side TEXT NOT NULL,
                entry REAL NOT NULL,
                sl REAL NOT NULL,
                tp1 REAL NOT NULL,
                tp2 REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                exit_price REAL,
                result_r REAL
            )
            """
        )
        self._conn.commit()

    def open_signal(self, event: SignalEvent) -> bool:
        ts = event.trigger_ts
        if isinstance(ts, pd.Timestamp):
            ts = ts.isoformat()
        elif isinstance(ts, datetime):
            ts = ts.isoformat()
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO tracked_signals
                (dedupe_key, symbol, setup, side, entry, sl, tp1, tp2, status, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """,
            (
                event.dedupe_key,
                event.symbol,
                event.setup,
                event.side,
                float(event.entry),
                float(event.sl),
                float(event.tp1),
                float(event.tp2),
                str(ts),
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def open_signals(self) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM tracked_signals WHERE status = 'OPEN' ORDER BY opened_at"
        )
        return cur.fetchall()

    def evaluate(
        self,
        df: pd.DataFrame,
        now: datetime | pd.Timestamp | None = None,
        max_hold_minutes: int = 1440,
        commit: bool = True,
    ) -> list[Update]:
        updates: list[Update] = []
        now_ts = pd.Timestamp(now) if now else df.index[-1]
        cutoff = now_ts - pd.Timedelta(minutes=max_hold_minutes)

        for row in self.open_signals():
            opened = pd.Timestamp(row["opened_at"])
            bars = df[df.index > opened]
            if bars.empty:
                continue

            status: str | None = None
            exit_price = 0.0
            exit_ts = bars.index[-1]

            for ts, bar in bars.iterrows():
                if row["side"] == "long":
                    if float(bar["low"]) <= row["sl"]:
                        status, exit_price, exit_ts = "SL", float(row["sl"]), ts
                        break
                    if float(bar["high"]) >= row["tp1"]:
                        status, exit_price, exit_ts = "TP1", float(row["tp1"]), ts
                        break
                else:
                    if float(bar["high"]) >= row["sl"]:
                        status, exit_price, exit_ts = "SL", float(row["sl"]), ts
                        break
                    if float(bar["low"]) <= row["tp1"]:
                        status, exit_price, exit_ts = "TP1", float(row["tp1"]), ts
                        break

            if status is None and opened <= cutoff:
                status = "EXPIRED"
                exit_price = float(bars["close"].iloc[-1])
                exit_ts = bars.index[-1]

            if status is None:
                continue

            risk = (
                float(row["entry"]) - float(row["sl"])
                if row["side"] == "long"
                else float(row["sl"]) - float(row["entry"])
            )
            if risk <= 0:
                continue
            direction = 1.0 if row["side"] == "long" else -1.0
            result_r = direction * (exit_price - float(row["entry"])) / risk

            update = Update(
                key=row["dedupe_key"],
                symbol=row["symbol"],
                setup=row["setup"],
                side=row["side"],
                entry=float(row["entry"]),
                sl=float(row["sl"]),
                tp1=float(row["tp1"]),
                status=status,
                exit_price=exit_price,
                result_r=result_r,
                opened_at=row["opened_at"],
            )
            updates.append(update)

            if commit:
                self._conn.execute(
                    """
                    UPDATE tracked_signals
                       SET status = ?, closed_at = ?, exit_price = ?, result_r = ?
                     WHERE dedupe_key = ?
                    """,
                    (status, str(exit_ts), exit_price, result_r, row["dedupe_key"]),
                )

        if commit:
            self._conn.commit()
        return updates

    def close(self) -> None:
        self._conn.close()
