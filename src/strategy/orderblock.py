from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class OrderBlock:
    side: str
    low: float
    high: float
    index: int
    ts: object = None
    fresh: bool = True

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


def _touched(df: pd.DataFrame, ob: OrderBlock) -> bool:
    after = df.iloc[ob.index + 1 :]
    if after.empty:
        return False
    if ob.side == "long":
        return bool((after["low"] <= ob.high).any())
    return bool((after["high"] >= ob.low).any())


def find_order_blocks(
    df: pd.DataFrame,
    atr_series: pd.Series,
    displacement_mult: float = 1.2,
    lookback: int = 60,
) -> list[OrderBlock]:
    results: list[OrderBlock] = []
    start = max(1, len(df) - lookback)
    for i in range(start, len(df) - 1):
        atr_value = float(atr_series.iloc[i + 1])
        if atr_value <= 0:
            continue
        impulse = df.iloc[i + 1]
        body = abs(float(impulse["close"]) - float(impulse["open"]))
        if body < atr_value * displacement_mult:
            continue

        base = df.iloc[i]
        bullish_impulse = float(impulse["close"]) > float(impulse["open"])
        base_bearish = float(base["close"]) < float(base["open"])
        base_bullish = float(base["close"]) > float(base["open"])

        if bullish_impulse and base_bearish:
            ob = OrderBlock(
                side="long",
                low=float(base["low"]),
                high=float(base["high"]),
                index=i,
                ts=df.index[i],
            )
            ob.fresh = not _touched(df, ob)
            results.append(ob)
        elif not bullish_impulse and base_bullish:
            ob = OrderBlock(
                side="short",
                low=float(base["low"]),
                high=float(base["high"]),
                index=i,
                ts=df.index[i],
            )
            ob.fresh = not _touched(df, ob)
            results.append(ob)
    return results


def select_order_block(
    blocks: list[OrderBlock], side: str, price: float, fresh_only: bool = True
) -> OrderBlock | None:
    candidates = [b for b in blocks if b.side == side]
    if fresh_only:
        candidates = [b for b in candidates if b.fresh]
    if not candidates:
        return None
    return min(candidates, key=lambda b: abs(b.mid - price) )
