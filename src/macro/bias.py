from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BiasReport:
    score: int
    label: str
    factors: dict[str, float] = field(default_factory=dict)

    @property
    def direction(self) -> int:
        if self.score >= 20:
            return 1
        if self.score <= -20:
            return -1
        return 0


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def label_for(score: int) -> str:
    if score >= 50:
        return "BULLISH_STRONG"
    if score >= 20:
        return "BULLISH"
    if score <= -50:
        return "BEARISH_STRONG"
    if score <= -20:
        return "BEARISH"
    return "NEUTRAL"


def score_from_inputs(
    real_yield_delta_5d: float | None = None,
    dxy_return_5d: float | None = None,
    fed_score: float = 0.0,
    t10yie_delta_20d: float | None = None,
    gdelt_tone: float | None = None,
    cb_score: float = 0.0,
    etf_flow_5d: float | None = None,
) -> BiasReport:
    """Weights follow docs/06-macro-news-engine.md §2 (sum = 100)."""
    factors: dict[str, float] = {}

    if real_yield_delta_5d is not None:
        factors["real_yield"] = 25 * _clip(-real_yield_delta_5d / 0.15)
    if dxy_return_5d is not None:
        factors["dxy"] = 20 * _clip(-dxy_return_5d / 1.0)
    factors["fed_path"] = 15 * _clip(fed_score)
    if t10yie_delta_20d is not None:
        factors["breakeven"] = 10 * _clip(t10yie_delta_20d / 0.20)
    if gdelt_tone is not None:
        factors["geo"] = 15 * _clip(-gdelt_tone / 5.0, 0.0, 1.0)
    factors["cb_buying"] = 10 * _clip(cb_score)
    if etf_flow_5d is not None:
        factors["etf_flow"] = 5 * _clip(etf_flow_5d / 5.0)

    score = round(sum(factors.values()))
    score = max(-100, min(100, score))
    return BiasReport(score=score, label=label_for(score), factors=factors)
