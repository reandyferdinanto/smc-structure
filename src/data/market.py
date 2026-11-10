from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import binance_paxg, gold_api
from .base import DataError, SpotQuote
from .cache import load_csv, save_csv
from .normalizer import validate_ohlcv
from ..config import ROOT
from ..utils.log import get_logger

log = get_logger("data.market")


class MarketData:
    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else ROOT / "data"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def ohlcv(self, tf: str = "15m", limit: int = 500) -> pd.DataFrame:
        try:
            frame = binance_paxg.fetch_ohlcv(tf=tf, limit=limit)
            frame = validate_ohlcv(frame, min_bars=30)
            save_csv(frame, self.cache_dir / f"paxg_{tf}.csv")
            return frame
        except DataError as exc:
            log.warning("primary source failed (%s), trying cache", exc)
            cached = self.cache_dir / f"paxg_{tf}.csv"
            if cached.exists():
                frame = validate_ohlcv(load_csv(cached), min_bars=30)
                log.warning("using stale cache for %s", tf)
                return frame
            raise

    def spot(self) -> SpotQuote | None:
        try:
            return gold_api.fetch_quote()
        except DataError as exc:
            log.warning("spot quote unavailable: %s", exc)
            return None

    def basis_pct(self, frame: pd.DataFrame, spot: SpotQuote | None = None) -> float | None:
        quote = spot or self.spot()
        if quote is None or frame.empty:
            return None
        last_close = float(frame["close"].iloc[-1])
        if last_close <= 0:
            return None
        return (quote.price / last_close - 1.0) * 100.0
