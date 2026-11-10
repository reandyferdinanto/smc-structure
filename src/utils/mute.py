from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import ROOT


def _path(state_dir: str | Path | None) -> Path:
    base = Path(state_dir) if state_dir else ROOT / "state"
    base.mkdir(parents=True, exist_ok=True)
    return base / "mute_until"


def mute(minutes: int, state_dir: str | Path | None = None) -> datetime:
    until = datetime.now(UTC) + timedelta(minutes=max(1, minutes))
    _path(state_dir).write_text(until.isoformat(), encoding="utf-8")
    return until


def unmute(state_dir: str | Path | None = None) -> None:
    path = _path(state_dir)
    if path.exists():
        path.unlink()


def until(state_dir: str | Path | None = None) -> datetime | None:
    path = _path(state_dir)
    if not path.exists():
        return None
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def is_muted(state_dir: str | Path | None = None, now: datetime | None = None) -> bool:
    target = until(state_dir)
    if target is None:
        return False
    return (now or datetime.now(UTC)) < target
