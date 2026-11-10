from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

from ..config import Config, ROOT
from ..data.market import MarketData
from ..macro.calendar import fetch_events, next_high_impact
from ..strategy.bollinger import add_bollinger, atr, is_squeeze, percentile_rank
from ..strategy.engine import Engine
from ..strategy.reentry import evaluate as evaluate_reentry
from ..strategy.regime import classify
from ..utils import mute
from ..utils.log import get_logger
from ..utils.time import (
    fmt_wib_utc,
    session_display,
    session_label,
    to_wib,
    to_wib_str,
    utcnow,
)
from . import telegram
from .tracker import TradeTracker

log = get_logger("alerts.commands")

API = "https://api.telegram.org"

HELP_TEXT = """<b>\U0001f916 XAUUSD Alert Bot \u2014 Panduan</b>
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
<b>Alur alert</b>
1. \U0001f7e1 <b>SETUP</b> \u2014 belum entry. Tunggu pesan OPEN.
2. \U0001f7e2/\U0001f534 <b>OPEN \u2026 NOW</b> \u2014 eksekusi sekarang.
3. \u2705/\u274c <b>TP1/SL</b> \u2014 update otomatis.

<b>Perintah</b>
/status \u2014 kondisi engine sekarang
/last \u2014 sinyal terakhir
/reentry \u2014 cek re-entry (BB mid M5)
/calendar \u2014 agenda high-impact hari ini
/mute 60 \u2014 hentikan alert 60 menit
/unmute \u2014 aktifkan lagi
/help \u2014 panduan ini

<b>Aturan penting</b>
\u2022 Jangan entry saat SETUP (belum konfirmasi M5)
\u2022 Jangan chase &gt;0.15 ATR dari zona
\u2022 Blackout \u00b130 menit news High USD
\u2022 Risk 0.25\u20130.5% per trade, maks 2 posisi

<i>Dokumentasi: docs/05-telegram-bot.md, docs/12-reentry.md</i>"""


class Commands:
    def __init__(self, config: Config | None = None, state_dir: str | Path | None = None):
        self.cfg = config or Config()
        self.state_dir = Path(state_dir) if state_dir else ROOT / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        allowed = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID", "")
        self.token = token
        self.allowed = {item.strip() for item in allowed.split(",") if item.strip()}
        self.offset_path = self.state_dir / "tg_offset"

    def poll(self) -> int:
        if not self.token:
            return 0

        if self.offset_path.exists():
            offset = int(self.offset_path.read_text(encoding="utf-8").strip() or "0")
        else:
            offset = 0
        try:
            response = httpx.get(
                f"{API}/bot{self.token}/getUpdates",
                params={"offset": offset, "limit": 20, "timeout": 0},
                timeout=15,
            )
            result = response.json().get("result", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("getUpdates failed: %s", exc)
            return 0

        handled = 0
        for update in result:
            offset = int(update["update_id"]) + 1
            message = update.get("message") or {}
            chat_id = str((message.get("chat") or {}).get("id", ""))
            text = (message.get("text") or "").strip()
            if not text.startswith("/"):
                continue
            if self.allowed and chat_id not in self.allowed:
                log.warning("command from unknown chat %s ignored", chat_id)
                continue
            reply = self._handle(text.split("@", 1)[0].lower(), text)
            if reply:
                telegram.send(reply, chat_id=chat_id)
                handled += 1
        self.offset_path.write_text(str(offset), encoding="utf-8")
        if handled:
            log.info("commands handled: %d", handled)
        return handled

    def _handle(self, command: str, raw: str) -> str | None:
        command = command.split()[0].split("@", 1)[0].lower() if command else ""
        if command == "/help" or command == "/start":
            return HELP_TEXT
        if command == "/status":
            return self._status()
        if command == "/last":
            return self._last()
        if command == "/reentry":
            return self._reentry()
        if command == "/calendar":
            return self._calendar()
        if command == "/mute":
            parts = raw.split()
            minutes = 60
            if len(parts) > 1:
                try:
                    minutes = max(1, int(parts[1]))
                except ValueError:
                    return "Format: /mute 60 (menit)"
            target = mute.mute(minutes, self.state_dir)
            return f"\U0001f507 Alert dimatikan sampai {to_wib_str(target)}."
        if command == "/unmute":
            mute.unmute(self.state_dir)
            return "\U0001f50a Alert aktif kembali."
        return "Perintah tidak dikenal. Ketik /help."

    def _frames(self):
        market = MarketData()
        d15 = market.ohlcv("15m", 500).iloc[:-1]
        d1h = market.ohlcv("1h", 500).iloc[:-1]
        d4h = market.ohlcv("4h", 500).iloc[:-1]
        d5 = market.ohlcv("5m", 500).iloc[:-1]
        return market, d15, d1h, d4h, d5

    def _status(self) -> str:
        market, d15, d1h, d4h, _ = self._frames()
        engine = Engine(self.cfg)
        bb = add_bollinger(d1h, 20, 2.0)
        bias = engine.bias_h4(d4h)
        regime = classify(d1h).value
        squeeze = is_squeeze(bb, 100, 25, recent=6)
        rank = float(percentile_rank(bb["bb_width"], 100).iloc[-1])
        spot = market.spot()
        basis = market.basis_pct(d15, spot)
        now = utcnow()

        tracker = TradeTracker(self.state_dir / "signals.db")
        try:
            armed = len(tracker.list_armed())
            opened = len(tracker.open_signals())
            last = tracker.last_signal()
        finally:
            tracker.close()

        muted = mute.until(self.state_dir)
        lines = [
            f"\u2699\ufe0f <b>STATUS</b> \u2014 {fmt_wib_utc(now)}",
            f"Session: {session_display(session_label(now))}",
            f"Bias H4: <b>{bias:+d}</b> \u00b7 Regime: {regime}",
            f"Squeeze H1: {'ya' if squeeze else 'tidak'} (rank {rank:.0f})",
        ]
        if spot is not None:
            lines.append(f"Spot: <code>{spot.price:.2f}</code> \u00b7 basis {basis:+.2f}%")
        lines.append(f"Armed: {armed} \u00b7 Posisi: {opened}")
        lines.append(
            f"Mute: {'aktif s/d ' + to_wib_str(muted) if muted else 'tidak aktif'}"
        )
        if last is not None:
            lines.append(
                f"Terakhir: {last['side']} {last['setup']} \u00b7 {last['status']}"
            )
        return "\n".join(lines)

    def _last(self) -> str:
        tracker = TradeTracker(self.state_dir / "signals.db")
        try:
            row = tracker.last_signal()
        finally:
            tracker.close()
        if row is None:
            return "Belum ada sinyal tersimpan."
        return "\n".join(
            [
                f"\U0001f4cc <b>SINYAL TERAKHIR</b> \u2014 {row['symbol']}",
                f"{row['setup']} \u00b7 {row['side']} \u00b7 status <b>{row['status']}</b>",
                f"Zona <code>{float(row['zone_low']):.2f}\u2013{float(row['zone_high']):.2f}</code>",
                f"SL <code>{float(row['sl']):.2f}</code> \u00b7 TP1 <code>{float(row['tp1']):.2f}</code>",
                f"Waktu {to_wib_str(datetime.fromisoformat(str(row['ts'])))}",
            ]
        )

    def _reentry(self) -> str:
        tracker = TradeTracker(self.state_dir / "signals.db")
        try:
            row = tracker.last_signal()
        finally:
            tracker.close()
        if row is None:
            return "Belum ada sinyal untuk referensi re-entry."

        market = MarketData()
        frame = market.ohlcv("5m", 500).iloc[:-1]
        result = evaluate_reentry(
            frame,
            side=row["side"],
            zone_low=float(row["zone_low"]),
            zone_high=float(row["zone_high"]),
            tp1=float(row["tp1"]),
            tp2=float(row["tp2"]),
            atr_value=float(atr(frame, 14).iloc[-1]),
            invalid_level=float(row["sl"]),
        )
        if not result.valid:
            reasons = {
                "no_bb_mid_bounce": "Harga belum bounce di BB middle.",
                "too_late": "Terlalu dekat TP1 (sisa RR jelek).",
                "rr_too_low": "RR sisa di bawah 1.2.",
                "below_invalidation": "Harga sudah di bawah level invalid.",
                "above_invalidation": "Harga sudah di atas level invalid.",
                "no_signal_in_db": "Belum ada sinyal.",
            }
            return f"\U0001f6ab Re-entry tidak valid: {reasons.get(result.reason, result.reason)}"
        return "\n".join(
            [
                f"\U0001f501 <b>RE-ENTRY {result.side.upper()}</b> valid",
                f"Entry <code>{result.entry:.2f}</code> \u00b7 SL <code>{result.sl:.2f}</code>",
                f"TP1 <code>{result.tp1:.2f}</code> \u00b7 RR <b>{result.rr:.2f}</b>",
                f"<i>{fmt_wib_utc(utcnow())}</i>",
            ]
        )

    def _calendar(self) -> str:
        events = fetch_events()
        now = utcnow()
        start = to_wib(now).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        todays = [
            event
            for event in events
            if start <= to_wib(event.ts_utc) < end
            and event.currency == "USD"
            and event.impact == "High"
        ]
        if not todays:
            return "\U0001f4c5 Tidak ada event High USD hari ini."
        lines = ["\U0001f4c5 <b>Agenda High USD hari ini (WIB)</b>"]
        for event in sorted(todays, key=lambda item: item.ts_utc):
            lines.append(
                f"{fmt_wib_utc(event.ts_utc, '%H:%M')} \u2014 {event.title}"
            )
        return "\n".join(lines)
