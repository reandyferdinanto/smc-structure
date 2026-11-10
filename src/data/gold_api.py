from __future__ import annotations

from datetime import datetime

import httpx

from .base import DataError, SpotQuote

URL = "https://api.gold-api.com/price/XAU"


def fetch_quote(timeout: float = 10.0) -> SpotQuote:
    try:
        response = httpx.get(URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        ts = datetime.fromisoformat(str(payload["updatedAt"]).replace("Z", "+00:00"))
        return SpotQuote(
            symbol=str(payload.get("symbol", "XAU")),
            price=float(payload["price"]),
            ts_utc=ts,
            source="gold-api",
        )
    except Exception as exc:  # noqa: BLE001
        raise DataError(f"gold-api failed: {exc}") from exc
