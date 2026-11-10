from __future__ import annotations

from datetime import datetime

from ..strategy.types import SignalEvent
from ..utils.time import fmt_wib_utc, session_display, to_wib_str, utcnow


def render_entry(event: SignalEvent, basis_pct: float | None = None) -> str:
    icon = "\U0001f7e2" if event.side == "long" else "\U0001f534"
    side = event.side.upper()
    lines = [
        f"{icon} <b>{event.symbol} {side}</b> \u00b7 {event.setup} \u00b7 {event.tf}",
        "\u2501" * 12,
        f"Entry   <code>{event.entry:.2f}</code>",
        f"SL      <code>{event.sl:.2f}</code>",
        f"TP1     <code>{event.tp1:.2f}</code>",
        f"TP2     <code>{event.tp2:.2f}</code>",
        "",
        f"RR <b>{event.rr:.2f}</b> \u00b7 Confidence <b>{event.confidence}%</b>",
        f"Session {session_display(event.session)} \u00b7 Regime {event.regime}",
    ]
    if event.reasons:
        lines.append("")
        lines.append("<b>Alasan</b>")
        lines.extend(f"\u2022 {reason}" for reason in event.reasons)
    if basis_pct is not None:
        lines.append(f"Basis PAXG {basis_pct:+.2f}%")
    lines.append("")
    lines.append(f"<i>{to_wib_str(event.trigger_ts)} \u00b7 python</i>")
    return "\n".join(lines)


def render_watchlist(event: SignalEvent) -> str:
    return (
        f"\U0001f7e1 <b>{event.symbol} \u2014 WATCHLIST</b> ({event.confidence}%)\n"
        f"Setup {event.setup} \u00b7 {event.side} \u00b7 entry {event.entry:.2f}\n"
        f"{', '.join(event.reasons[:4])}"
    )


def render_setup(event: SignalEvent) -> str:
    icon = "\U0001f7e1"
    side = event.side.upper()
    zone_low = event.zone_low if event.zone_low is not None else event.entry
    zone_high = event.zone_high if event.zone_high is not None else event.entry
    lines = [
        f"{icon} <b>{event.symbol} SETUP {side}</b> \u00b7 {event.setup}",
        "\u2501" * 12,
        f"Zona    <code>{zone_low:.2f} \u2013 {zone_high:.2f}</code>",
        f"Invalid <code>{event.sl:.2f}</code>",
        f"TP1 <code>{event.tp1:.2f}</code> \u00b7 TP2 <code>{event.tp2:.2f}</code>",
        "",
        "<b>Belum entry.</b> Tunggu pesan <b>OPEN \u2026 NOW</b> setelah konfirmasi M5.",
        f"Confidence {event.confidence}% \u00b7 {session_display(event.session)}",
        "",
        f"<i>Candle close {fmt_wib_utc(event.trigger_ts)}</i>",
        f"<i>Dikirim {fmt_wib_utc(utcnow(), '%d %b %Y %H:%M')}</i>",
    ]
    return "\n".join(lines)


def render_trigger(event: SignalEvent, reasons: list[str] | None = None) -> str:
    icon = "\U0001f7e2" if event.side == "long" else "\U0001f534"
    side = "LONG" if event.side == "long" else "SHORT"
    lines = [
        f"{icon} <b>OPEN {side} NOW \u2014 {event.symbol}</b>",
        "\u2501" * 12,
        f"Entry <code>{event.entry:.2f}</code>",
        f"SL    <code>{event.sl:.2f}</code>",
        f"TP1   <code>{event.tp1:.2f}</code>  RR <b>{event.rr:.2f}</b>",
        f"TP2   <code>{event.tp2:.2f}</code>",
        "",
        "Konfirmasi M5 valid. Eksekusi sekarang, jangan chase >0.15 ATR.",
        f"<i>Dikirim {fmt_wib_utc(utcnow())}</i>",
    ]
    if reasons:
        lines.append(f"<i>{' \u00b7 '.join(reasons)}</i>")
    return "\n".join(lines)


def render_volatility_warning(direction: str, price: float, ratio: float) -> str:
    arrow = "\u2b06\ufe0f" if direction == "up" else "\u2b07\ufe0f"
    return (
        f"\u26a1 <b>VOLATILITY SPIKE {arrow}</b>\n"
        f"Harga <code>{price:.2f}</code> \u00b7 range {ratio:.1f}\u00d7 normal\n"
        f"{fmt_wib_utc(utcnow())}\n"
        "<i>Entry baru ditahan sementara. Kemungkinan news mendadak.</i>"
    )


def render_prenews(event, minutes: int, open_positions: int) -> str:
    return (
        f"\U0001f534 <b>HIGH-IMPACT NEWS dalam {minutes} menit</b>\n"
        f"{event.title} ({event.currency})\n"
        f"Jadwal: <b>{fmt_wib_utc(event.ts_utc, '%H:%M')}</b>\n"
        f"Posisi terbuka: <b>{open_positions}</b>\n"
        "<i>Pertimbangkan tutup/kurangi posisi sebelum rilis. Entry baru diblokir "
        "\u00b130 menit.</i>"
    )


def render_cancel(event: SignalEvent, reason: str) -> str:
    side = event.side.upper()
    label = "EXPIRED" if reason == "expired" else "CANCELLED"
    return (
        f"\u26aa <b>{event.symbol} SETUP {side} \u2014 {label}</b>\n"
        f"Zona {event.zone_low:.2f}\u2013{event.zone_high:.2f} tidak terkonfirmasi.\n"
        f"<i>Tidak ada entry. Sinyal dihapus.</i>"
    )


def render_update(update) -> str:
    if update.status == "TP1":
        icon, title = "\u2705", "TP1 HIT"
    elif update.status == "SL":
        icon, title = "\u274c", "SL HIT"
    else:
        icon, title = "\u23f3", "EXPIRED"

    side = update.side.upper()
    lines = [
        f"{icon} <b>{update.symbol} {side} \u2014 {title}</b>",
        "\u2501" * 12,
        f"Entry  <code>{update.entry:.2f}</code>",
        f"Exit   <code>{update.exit_price:.2f}</code>",
        f"Result <b>{update.result_r:+.2f}R</b>",
        f"SL <code>{update.sl:.2f}</code> \u00b7 TP1 <code>{update.tp1:.2f}</code>",
        f"Setup {update.setup} \u00b7 opened {to_wib_str(datetime.fromisoformat(str(update.opened_at)))}",
    ]
    if update.status == "SL":
        lines.append("")
        lines.append("<i>Posisi ditutup di SL. Tidak ada aksi lanjutan.</i>")
    elif update.status == "TP1":
        lines.append("")
        lines.append("<i>Pertimbangkan tutup 50% dan pindahkan SL ke breakeven.</i>")
    return "\n".join(lines)
