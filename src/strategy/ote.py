from __future__ import annotations


def ote_zone(
    impulse_low: float,
    impulse_high: float,
    side: str,
    min_ret: float = 0.62,
    max_ret: float = 0.786,
) -> tuple[float, float]:
    leg = impulse_high - impulse_low
    if leg <= 0:
        return (impulse_low, impulse_high)
    if side == "long":
        return (impulse_high - max_ret * leg, impulse_high - min_ret * leg)
    return (impulse_low + min_ret * leg, impulse_low + max_ret * leg)


def in_zone(price: float, zone: tuple[float, float]) -> bool:
    low, high = sorted(zone)
    return low <= price <= high


def overlap(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float] | None:
    low = max(min(a), min(b))
    high = min(max(a), max(b))
    if low > high:
        return None
    return (low, high)
