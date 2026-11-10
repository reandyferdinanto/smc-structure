from __future__ import annotations

import pandas as pd
import httpx

from .base import DataError, OHLCV_COLUMNS

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "PAXGUSDT"
ALLOWED_TF = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


def fetch_ohlcv(tf: str = "15m", limit: int = 500, timeout: float = 10.0) -> pd.DataFrame:
    if tf not in ALLOWED_TF:
        raise DataError(f"unsupported timeframe: {tf}")
    try:
        response = httpx.get(
            BASE_URL,
            params={"symbol": SYMBOL, "interval": tf, "limit": min(limit, 1000)},
            timeout=timeout,
        )
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:  # noqa: BLE001
        raise DataError(f"binance paxg failed: {exc}") from exc

    if not rows:
        raise DataError("binance paxg returned no rows")

    records = []
    for row in rows:
        records.append(
            {
                "ts": pd.to_datetime(row[0], unit="ms", utc=True),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )
    frame = pd.DataFrame.from_records(records).set_index("ts")
    return frame[OHLCV_COLUMNS].astype(float).sort_index()
