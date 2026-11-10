from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_csv(df: pd.DataFrame, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target)
    return target


def load_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["ts"], index_col="ts")
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")
    return frame
