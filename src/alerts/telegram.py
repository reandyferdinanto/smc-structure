from __future__ import annotations

import os

import httpx

from ..utils.log import get_logger

log = get_logger("alerts.telegram")


def send(
    text: str,
    token: str | None = None,
    chat_id: str | None = None,
    timeout: float = 10.0,
) -> bool:
    bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    target = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not target:
        log.warning("telegram credentials missing; message not sent")
        return False

    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": target,
                "text": text[:4096],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        if response.status_code == 429:
            log.warning("telegram rate limited")
            return False
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("telegram send failed: %s", exc)
        return False
