from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"


class Config:
    def __init__(self, path: str | Path | None = None):
        raw_path = path or os.getenv("CONFIG_PATH") or DEFAULT_CONFIG
        p = Path(raw_path)
        if not p.is_absolute():
            p = ROOT / p
        self.path = p
        self.data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}

    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, name: str) -> dict:
        value = self.data.get(name)
        return value if isinstance(value, dict) else {}


def load_env_file(path: str | Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE, no interpolation) so scripts work without extra deps."""
    target = Path(path) if path else ROOT / ".env"
    if not target.exists():
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def dry_run() -> bool:
    return env_bool("DRY_RUN", True)
