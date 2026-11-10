from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .runner import Trade


@dataclass
class Metrics:
    trades: int
    wins: int
    win_rate: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    avg_rr_win: float
    total_r: float

    def as_dict(self) -> dict:
        return {
            "trades": self.trades,
            "wins": self.wins,
            "win_rate": round(self.win_rate, 3),
            "expectancy_r": round(self.expectancy_r, 3),
            "profit_factor": round(self.profit_factor, 3),
            "max_drawdown_r": round(self.max_drawdown_r, 3),
            "avg_rr_win": round(self.avg_rr_win, 3),
            "total_r": round(self.total_r, 3),
        }


def summarize(trades: list[Trade]) -> Metrics:
    if not trades:
        return Metrics(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    r = np.array([t.r_multiple for t in trades], dtype=float)
    wins = r[r > 0]
    losses = r[r <= 0]
    equity = np.cumsum(r)
    peaks = np.maximum.accumulate(np.concatenate([[0.0], equity]))[1:]
    drawdown = peaks - equity
    gross_win = float(wins.sum())
    gross_loss = float(abs(losses.sum()))

    return Metrics(
        trades=len(trades),
        wins=len(wins),
        win_rate=len(wins) / len(trades),
        expectancy_r=float(r.mean()),
        profit_factor=gross_win / gross_loss if gross_loss > 0 else float("inf"),
        max_drawdown_r=float(drawdown.max()) if len(drawdown) else 0.0,
        avg_rr_win=float(wins.mean()) if len(wins) else 0.0,
        total_r=float(r.sum()),
    )
