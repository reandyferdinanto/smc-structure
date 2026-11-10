from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.data import fetch_history
from src.backtest.metrics import summarize
from src.backtest.runner import run_backtest
from src.data.cache import load_csv, save_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest XAUUSD (PAXG proxy) M15")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--every", type=int, default=4, help="evaluate every N bars")
    parser.add_argument("--window", type=int, default=600)
    parser.add_argument("--max-hold", type=int, default=96)
    parser.add_argument("--spread", type=float, default=0.35)
    parser.add_argument("--csv", type=str, default="")
    parser.add_argument("--tag", type=str, default="quick")
    args = parser.parse_args()

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    if args.csv:
        frame = load_csv(args.csv)
    else:
        cache = data_dir / f"history_15m_{args.days}d.csv"
        if cache.exists():
            frame = load_csv(cache)
        else:
            frame = fetch_history(tf="15m", days=args.days)
            save_csv(frame, cache)
        print(f"bars={len(frame)} from {frame.index[0]} to {frame.index[-1]}")

    trades = run_backtest(
        frame,
        window=args.window,
        every=args.every,
        max_hold=args.max_hold,
        spread=args.spread,
    )
    metrics = summarize(trades)
    print(metrics.as_dict())

    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    out = reports / f"backtest_{args.tag}.csv"
    if trades:
        import pandas as pd

        pd.DataFrame([t.__dict__ for t in trades]).to_csv(out, index=False)
        print(f"trades written to {out}")


if __name__ == "__main__":
    main()
