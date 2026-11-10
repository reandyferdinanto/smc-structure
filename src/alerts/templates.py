from __future__ import annotations

from datetime import datetime

from ..strategy.types import SignalEvent
from ..utils.time import session_display, to_wib_str


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
