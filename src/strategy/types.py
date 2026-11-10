from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass
class SignalEvent:
    symbol: str
    setup: str
    side: str
    tf: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr: float
    confidence: int
    reasons: list[str] = field(default_factory=list)
    session: str = ""
    regime: str = ""
    trigger_ts: datetime | None = None
    zone_low: float | None = None
    zone_high: float | None = None

    @property
    def dedupe_key(self) -> str:
        import hashlib

        raw = f"{self.symbol}|{self.setup}|{self.side}|{self.tf}|{self.trigger_ts}"
        return hashlib.sha1(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        ts = self.trigger_ts
        if isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()
        return {
            "type": "entry",
            "symbol": self.symbol,
            "setup": self.setup,
            "side": self.side,
            "tf": self.tf,
            "entry": round(self.entry, 2),
            "sl": round(self.sl, 2),
            "tp1": round(self.tp1, 2),
            "tp2": round(self.tp2, 2),
            "rr": round(self.rr, 2),
            "confidence": self.confidence,
            "reasons": self.reasons,
            "session": self.session,
            "regime": self.regime,
            "trigger_candle_ts": ts.isoformat() if ts else None,
            "zone_low": round(self.zone_low, 2) if self.zone_low is not None else None,
            "zone_high": round(self.zone_high, 2) if self.zone_high is not None else None,
            "source": "python",
        }
