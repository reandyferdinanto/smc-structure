from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.alerts import telegram
from src.alerts.templates import render_reentry
from src.alerts.tracker import TradeTracker
from src.config import Config, dry_run, load_env_file
from src.data.market import MarketData
from src.strategy.bollinger import atr
from src.strategy.reentry import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-entry check for the last signal")
    parser.add_argument("--tf", default="5m", choices=["m1", "1m", "m5", "5m"])
    parser.add_argument("--send", action="store_true", help="send to Telegram if valid")
    parser.add_argument("--min-rr", type=float, default=1.2)
    parser.add_argument("--max-progress", type=float, default=0.70)
    args = parser.parse_args()

    load_env_file()
    cfg = Config()
    tf = "1m" if args.tf in {"m1", "1m"} else "5m"

    tracker = TradeTracker()
    try:
        row = tracker.last_signal()
    finally:
        tracker.close()

    if row is None:
        print(json.dumps({"valid": False, "reason": "no_signal_in_db"}))
        return

    market = MarketData()
    frame = market.ohlcv(tf, 500).iloc[:-1]
    atr_value = float(atr(frame, 14).iloc[-1])
    result = evaluate(
        frame,
        side=row["side"],
        zone_low=float(row["zone_low"]),
        zone_high=float(row["zone_high"]),
        tp1=float(row["tp1"]),
        tp2=float(row["tp2"]),
        atr_value=atr_value,
        min_rr=args.min_rr,
        max_progress=args.max_progress,
        invalid_level=float(row["sl"]),
    )

    payload = {
        "valid": result.valid,
        "reason": result.reason,
        "symbol": row["symbol"],
        "setup": row["setup"],
        "side": result.side,
        "entry": round(result.entry, 2),
        "sl": round(result.sl, 2),
        "tp1": round(result.tp1, 2),
        "tp2": round(result.tp2, 2),
        "rr": round(result.rr, 2),
        "timeframe": tf,
    }
    print(json.dumps(payload))

    if result.valid and (args.send or not dry_run()):
        text = render_reentry(result, row["symbol"])
        print("sent" if telegram.send(text) else "send failed")


if __name__ == "__main__":
    main()
