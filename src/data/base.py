from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpotQuote:
    symbol: str
    price: float
    ts_utc: datetime
    source: str


class DataAdapter(Protocol):
    name: str

    def fetch_ohlcv(self, tf: str, limit: int) -> pd.DataFrame: ...

    def fetch_quote(self) -> SpotQuote: ...
