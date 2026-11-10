from __future__ import annotations

import time

import httpx
import pandas as pd

from ..data.base import DataError, OHLCV_COLUMNS

BASE_URL = "https://data-api.binance.vision/api/v3/klines"


def fetch_history(
    tf: str = "15m",
    days: int = 90,
    symbol: str = "PAXGUSDT",
    timeout: float = 20.0,
) -> pd.DataFrame:
    """Paginated OHLCV download from Binance Vision (max 1000 bars per request)."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 86_400_000
    cursor = start_ms
    rows: list[list] = []

    while cursor <= end_ms:
        response = httpx.get(
            BASE_URL,
            params={
                "symbol": symbol,
                "interval": tf,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1000,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        cursor = int(batch[-1][0]) + 1

    if not rows:
        raise DataError("history download returned no rows")

    records = [
        {
            "ts": pd.to_datetime(row[0], unit="ms", utc=True),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in rows
    ]
    frame = pd.DataFrame.from_records(records).set_index("ts")
    frame = frame[OHLCV_COLUMNS].astype(float).sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame
