from __future__ import annotations

import argparse
import time
from datetime import datetime

import pandas as pd

from .alerts import templates, telegram
from .alerts.commands import Commands
from .alerts.dedupe import Dedupe
from .alerts.tracker import TradeTracker
from .config import Config, dry_run, load_env_file
from .data.market import MarketData
from .macro import guard
from .macro.calendar import blackout, fetch_events, next_high_impact
from .strategy import trigger
from .strategy.engine import Engine
from .strategy.trigger import ArmedSetup
from .strategy.types import SignalEvent
from .utils.log import get_logger
from .utils.time import to_wib_str, utcnow
from .utils import mute

log = get_logger("main")

TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}


def closed_bars(frame: pd.DataFrame, tf: str, now: datetime) -> pd.DataFrame:
    if frame.empty:
        return frame
    cutoff = pd.Timestamp(now) - pd.Timedelta(minutes=TF_MINUTES[tf])
    return frame[frame.index <= cutoff]


def _row_to_event(row) -> SignalEvent:
    return SignalEvent(
        symbol=row["symbol"],
        setup=row["setup"],
        side=row["side"],
        tf="15m",
        entry=(float(row["zone_low"]) + float(row["zone_high"])) / 2.0,
        sl=float(row["sl"]),
        tp1=float(row["tp1"]),
        tp2=float(row["tp2"]),
        rr=0.0,
        confidence=int(row["confidence"]),
        reasons=[],
        session=row["session"] or "",
        regime=row["regime"] or "",
        trigger_ts=pd.Timestamp(row["created_at"]),
        zone_low=float(row["zone_low"]),
        zone_high=float(row["zone_high"]),
    )


def _row_to_armed(row) -> ArmedSetup:
    return ArmedSetup(
        key=row["dedupe_key"],
        symbol=row["symbol"],
        setup=row["setup"],
        side=row["side"],
        zone_low=float(row["zone_low"]),
        zone_high=float(row["zone_high"]),
        sl=float(row["sl"]),
        tp1=float(row["tp1"]),
        tp2=float(row["tp2"]),
        confidence=int(row["confidence"]),
        session=row["session"] or "",
        regime=row["regime"] or "",
    )


def process_armed(
    tracker: TradeTracker,
    df_trigger: pd.DataFrame,
    now: datetime,
    should_send: bool,
    is_blackout: bool,
    cfg: Config,
    volatile: bool = False,
) -> None:
    tcfg = cfg.section("trigger")
    atr_trigger = trigger.atr_now(df_trigger)
    if atr_trigger <= 0:
        return

    for row in tracker.list_armed():
        event = _row_to_event(row)
        expires_at = pd.Timestamp(row["expires_at"])

        if pd.Timestamp(now) > expires_at:
            log.info("armed expired: %s %s", event.symbol, event.side)
            if should_send:
                if telegram.send(templates.render_cancel(event, "expired")):
                    tracker.set_armed_status(row["dedupe_key"], "EXPIRED")
            continue

        armed = _row_to_armed(row)
        if trigger.invalidated(df_trigger, armed):
            log.info("armed invalidated: %s %s", event.symbol, event.side)
            if should_send:
                if telegram.send(templates.render_cancel(event, "cancelled")):
                    tracker.set_armed_status(row["dedupe_key"], "CANCELLED")
            continue

        if is_blackout or volatile:
            continue

        result = trigger.confirm(
            df_trigger,
            armed,
            atr_trigger,
            zone_tol_mult=float(tcfg.get("zone_tolerance_atr", 0.10)),
            min_body_mult=float(tcfg.get("min_body_atr", 0.40)),
            max_chase_mult=float(tcfg.get("max_chase_atr", 0.15)),
            sweep_lookback=int(tcfg.get("sweep_lookback", 6)),
            min_rr=float(tcfg.get("min_rr", 1.2)),
        )
        if result is None:
            continue

        trigger_event = SignalEvent(
            symbol=armed.symbol,
            setup=armed.setup,
            side=armed.side,
            tf=str(tcfg.get("timeframe", "5m")),
            entry=result.entry,
            sl=result.sl,
            tp1=result.tp1,
            tp2=result.tp2,
            rr=result.rr,
            confidence=armed.confidence,
            reasons=result.reasons,
            session=armed.session,
            regime=armed.regime,
            trigger_ts=pd.Timestamp(now),
            zone_low=armed.zone_low,
            zone_high=armed.zone_high,
        )
        log.info("trigger %s", trigger_event.to_dict())
        if not should_send:
            continue
        if telegram.send(templates.render_trigger(trigger_event, result.reasons)):
            tracker.open_signal(trigger_event)
            tracker.set_armed_status(row["dedupe_key"], "TRIGGERED")


def run_once(config: Config | None = None, send: bool | None = None) -> dict | None:
    cfg = config or Config()
    engine = Engine(cfg)
    market = MarketData()
    now = utcnow()
    should_send = send if send is not None else not dry_run()
    if mute.is_muted():
        log.info("muted: trade alerts suppressed")
        should_send = False

    frames = {
        tf: closed_bars(market.ohlcv(tf, 500), tf, now)
        for tf in ("15m", "1h", "4h")
    }
    df15, df1h, df4h = frames["15m"], frames["1h"], frames["4h"]

    trigger_tf = str(cfg.get("trigger.timeframe", "5m"))
    if trigger_tf not in TF_MINUTES:
        trigger_tf = "5m"
    df_trigger = closed_bars(market.ohlcv(trigger_tf, 500), trigger_tf, now)
    log.info(
        "bars trigger(%s)=%d 15m=%d 1h=%d 4h=%d",
        trigger_tf,
        len(df_trigger),
        len(df15),
        len(df1h),
        len(df4h),
    )

    spot = market.spot()
    basis = market.basis_pct(df15, spot)
    if basis is not None:
        log.info("spot=%s basis=%.2f%%", f"{spot.price:.2f}" if spot else "-", basis)

    news_cfg = cfg.section("news")
    df1 = closed_bars(market.ohlcv("1m", 500), "1m", now)
    if news_cfg.get("spike_guard", True) and len(df1) > 0:
        spike = guard.detect_spike(
            df1,
            int(news_cfg.get("spike_lookback", 14)),
            float(news_cfg.get("spike_range_mult", 3.0)),
            float(news_cfg.get("spike_body_mult", 2.5)),
        )
    else:
        spike = guard.Spike(False, 0.0, 0.0, "")
    if spike.detected:
        log.warning(
            "volatility spike: direction=%s range_ratio=%.1f body_ratio=%.1f",
            spike.direction,
            spike.range_ratio,
            spike.body_ratio,
        )

    calendar_ok = True
    is_blackout = False
    upcoming = None
    try:
        events = fetch_events()
        is_blackout, _ = blackout(
            events,
            now,
            minutes=int(news_cfg.get("blackout_minutes", 30)),
            currencies=tuple(news_cfg.get("currencies", ["USD"])),
            impacts=tuple(news_cfg.get("impacts", ["High"])),
        )
        upcoming = next_high_impact(
            events,
            now,
            minutes=int(news_cfg.get("pre_news_warn_minutes", 15)),
            currencies=tuple(news_cfg.get("currencies", ["USD"])),
            impacts=tuple(news_cfg.get("impacts", ["High"])),
        )
    except Exception as exc:  # noqa: BLE001
        calendar_ok = False
        log.warning("calendar unavailable: %s", exc)

    tracker = TradeTracker()
    try:
        updates = tracker.evaluate(df15, now, commit=should_send)
        for update in updates:
            log.info(
                "update %s %s %s r=%.2f",
                update.symbol,
                update.side,
                update.status,
                update.result_r,
            )
            if should_send:
                telegram.send(templates.render_update(update))

        open_count = len(tracker.open_signals())
        armed_count = len(tracker.list_armed())
        alert_dedupe = Dedupe()
        try:
            if spike.detected and should_send and (open_count or armed_count):
                key = f"spike:{pd.Timestamp(now).floor('15min')}"
                if alert_dedupe.is_new(key):
                    text = templates.render_volatility_warning(
                        spike.direction, float(df1["close"].iloc[-1]), spike.range_ratio
                    )
                    if telegram.send(text):
                        alert_dedupe.mark(key, "spike")
            if upcoming is not None and should_send and (open_count or armed_count):
                key = f"prewarn:{upcoming.ts_utc.isoformat()}"
                if alert_dedupe.is_new(key):
                    minutes = max(
                        1, int((upcoming.ts_utc - pd.Timestamp(now).to_pydatetime()).total_seconds() / 60)
                    )
                    if telegram.send(
                        templates.render_prenews(upcoming, minutes, open_count)
                    ):
                        alert_dedupe.mark(key, "prenews")
        finally:
            alert_dedupe.close()

        process_armed(
            tracker, df_trigger, now, should_send, is_blackout, cfg, volatile=spike.detected
        )

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

        if spike.detected:
            log.warning("volatility spike -> new setup not armed")
            return payload

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
            if event.confidence < engine.conf_entry:
                if telegram.send(templates.render_watchlist(event)):
                    dedupe.mark(event.dedupe_key, str(payload))
                    log.info("watchlist sent")
                return payload
            if telegram.send(templates.render_setup(event)):
                dedupe.mark(event.dedupe_key, str(payload))
                tracker.arm(event, int(cfg.get("trigger.arm_expiry_minutes", 120)))
                log.info("setup armed")
        finally:
            dedupe.close()
        return payload
    finally:
        tracker.close()


def run_loop(config: Config | None = None) -> None:
    cfg = config or Config()
    log.info("loop started")
    while True:
        try:
            run_once(cfg)
        except Exception as exc:  # noqa: BLE001
            log.error("cycle failed: %s", exc)
        try:
            Commands(cfg).poll()
        except Exception as exc:  # noqa: BLE001
            log.warning("command poll failed: %s", exc)
        sleep_for = 60 - (time.time() % 60)
        time.sleep(max(5.0, sleep_for))


def main() -> None:
    parser = argparse.ArgumentParser(description="XAUUSD BB+SMC alert engine")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--loop", action="store_true", help="run forever on 60s cadence")
    parser.add_argument("--send", action="store_true", help="force sending even if DRY_RUN")
    args = parser.parse_args()

    load_env_file()
    cfg = Config()
    if args.once or not args.loop:
        payload = run_once(cfg, send=True if args.send else None)
        try:
            Commands(cfg).poll()
        except Exception as exc:  # noqa: BLE001
            log.warning("command poll failed: %s", exc)
        if payload:
            print(to_wib_str(utcnow()))
    else:
        run_loop(cfg)


if __name__ == "__main__":
    main()
