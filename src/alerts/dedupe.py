from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_PATH = Path("state/alerts.db")


class Dedupe:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_alerts (
                dedupe_key TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def is_new(self, key: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM sent_alerts WHERE dedupe_key = ?", (key,)
        )
        return cur.fetchone() is None

    def mark(self, key: str, payload: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO sent_alerts (dedupe_key, sent_at, payload) "
            "VALUES (?, datetime('now'), ?)",
            (key, payload),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
