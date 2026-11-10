from __future__ import annotations

import argparse
import time
from datetime import datetime

import pandas as pd

from .alerts import templates, telegram
from .alerts.dedupe import Dedupe
from .config import Config, dry_run
from .data.market import MarketData
from .macro.calendar import blackout, fetch_events
from .strategy.engine import Engine
from .utils.log import get_logger
from .utils.time import to_wib_str, utcnow

log = get_logger("main")

TF_MINUTES = {"15m": 15, "1h": 60, "4h": 240}


def closed_bars(frame: pd.DataFrame, tf: str, now: datetime) -> pd.DataFrame:
    if frame.empty:
        return frame
    cutoff = pd.Timestamp(now) - pd.Timedelta(minutes=TF_MINUTES[tf])
    return frame[frame.index <= cutoff]


def run_once(config: Config | None = None, send: bool | None = None) -> dict | None:
    cfg = config or Config()
    engine = Engine(cfg)
    market = MarketData()
    now = utcnow()

    frames = {tf: closed_bars(market.ohlcv(tf, 500), tf, now) for tf in ("15m", "1h", "4h")}
    df15, df1h, df4h = frames["15m"], frames["1h"], frames["4h"]
    log.info("bars 15m=%d 1h=%d 4h=%d", len(df15), len(df1h), len(df4h))

    spot = market.spot()
    basis = market.basis_pct(df15, spot)
    if basis is not None:
        log.info("spot=%s basis=%.2f%%", f"{spot.price:.2f}" if spot else "-", basis)

    calendar_ok = True
    is_blackout = False
    next_event = None
    try:
        events = fetch_events()
        is_blackout, next_event = blackout(events, now)
    except Exception as exc:  # noqa: BLE001
        calendar_ok = False
        log.warning("calendar unavailable: %s", exc)

    event = engine.evaluate(
        df15,
        df1h,
        df4h,
        macro_bias=None,
        blackout=is_blackout,
        now=now,
    )

    if event is None:
        log.info("no signal")
        return None

    payload = event.to_dict()
    log.info("signal %s", payload)

    should_send = send if send is not None else not dry_run()
    if not should_send or not calendar_ok:
        if not calendar_ok:
            log.warning("calendar stale -> suppressing alert (fail-closed)")
        else:
            log.info("dry-run: alert not sent")
        return payload

    dedupe = Dedupe()
    try:
        if not dedupe.is_new(event.dedupe_key):
            log.info("duplicate signal; skipped")
            return payload
        if event.confidence >= engine.conf_entry:
            text = templates.render_entry(event, basis)
        else:
            text = templates.render_watchlist(event)
        if telegram.send(text):
            dedupe.mark(event.dedupe_key, str(payload))
            log.info("alert sent (%s)", "entry" if event.confidence >= engine.conf_entry else "watchlist")
    finally:
        dedupe.close()
    return payload


def run_loop(config: Config | None = None) -> None:
    cfg = config or Config()
    log.info("loop started")
    while True:
        try:
            run_once(cfg)
        except Exception as exc:  # noqa: BLE001
            log.error("cycle failed: %s", exc)
        sleep_for = 60 - (time.time() % 60)
        time.sleep(max(5.0, sleep_for))


def main() -> None:
    parser = argparse.ArgumentParser(description="XAUUSD BB+SMC alert engine")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--loop", action="store_true", help="run forever on 60s cadence")
    parser.add_argument("--send", action="store_true", help="force sending even if DRY_RUN")
    args = parser.parse_args()

    cfg = Config()
    if args.once or not args.loop:
        payload = run_once(cfg, send=True if args.send else None)
        if payload:
            print(to_wib_str(utcnow()))
    else:
        run_loop(cfg)


if __name__ == "__main__":
    main()
