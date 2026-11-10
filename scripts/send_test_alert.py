from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.alerts import telegram
from src.alerts.templates import render_entry
from src.config import dry_run, load_env_file
from src.strategy.types import SignalEvent


def main() -> None:
    load_env_file()
    event = SignalEvent(
        symbol="XAUUSD",
        setup="A",
        side="long",
        tf="15m",
        entry=4112.70,
        sl=4105.47,
        tp1=4125.20,
        tp2=4134.00,
        rr=1.73,
        confidence=82,
        reasons=["bias_h4_+3", "regime_ranging", "h1_squeeze_p12", "sweep_4108.50", "fresh_ob"],
        session="overlap",
        regime="RANGING",
        trigger_ts=datetime(2026, 11, 10, 12, 30, tzinfo=timezone.utc),
    )
    text = render_entry(event, basis_pct=-0.33)
    print(text)
    if dry_run():
        print("\n[dry-run] DRY_RUN=true, message not sent")
        return
    ok = telegram.send(text)
    print("sent" if ok else "failed")


if __name__ == "__main__":
    main()
