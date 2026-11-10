from __future__ import annotations

from datetime import datetime

import pandas as pd

from ..config import Config
from ..utils.time import (
    in_killzone,
    session_label,
    session_score,
)
from .bollinger import add_bollinger, atr, is_squeeze, percentile_rank
from .fvg import find_fvgs, select_fvg
from .liquidity import equal_levels, find_sweep, nearest_above, nearest_below
from .orderblock import find_order_blocks, select_order_block
from .orb import breakout_side, build_session_range
from .regime import Regime, classify
from .structure import analyze, confirmation_after_sweep, displacement_after
from .swings import pivot_prices
from .types import SignalEvent


class Engine:
    def __init__(self, config: Config | None = None):
        self.cfg = config or Config()
        s = self.cfg.section("strategy")
        r = self.cfg.section("regime")
        o = self.cfg.section("orb")
        c = self.cfg.section("confidence")
        sess = self.cfg.section("sessions")

        self.symbol = str(self.cfg.get("symbols.name", "XAUUSD"))
        self.bb_length = int(s.get("bb_length", 20))
        self.bb_mult = float(s.get("bb_mult", 2.0))
        self.squeeze_lookback = int(s.get("squeeze_lookback", 100))
        self.squeeze_percentile = float(s.get("squeeze_percentile", 25))
        self.squeeze_recent = int(s.get("squeeze_recent", 6))
        self.sweep_lookback = int(s.get("sweep_lookback", 5))
        self.atr_length = int(s.get("atr_length", 14))
        self.disp_mult = float(s.get("displacement_atr_mult", 1.2))
        self.fvg_min_mult = float(s.get("fvg_min_atr_mult", 0.15))
        self.sweep_mult = float(s.get("sweep_atr_mult", 0.05))
        self.equal_mult = float(s.get("equal_level_atr_mult", 0.10))
        self.ote_min = float(s.get("ote_min", 0.62))
        self.ote_max = float(s.get("ote_max", 0.786))
        self.min_rr = float(s.get("min_rr", 1.5))
        self.pivot_major = int(s.get("pivot_k_major", 5))
        self.pivot_internal = int(s.get("pivot_k_internal", 2))
        self.ob_fresh_only = bool(s.get("ob_require_fresh", True))
        self.fvg_max_fill = float(s.get("fvg_max_fill_pct", 0.5))
        self.sl_pad = float(s.get("sl_padding_atr", 0.15))
        self.tp1_mult = float(s.get("tp1_atr_mult", 1.0))
        self.setup_a = bool(s.get("setup_a_enabled", True))
        self.setup_b = bool(s.get("setup_b_enabled", True))
        self.min_bars = int(s.get("max_bars_back", 500))

        self.adx_threshold = float(r.get("adx_trend_threshold", 25))
        self.atr_rank_vol = float(r.get("atr_rank_volatile", 80))
        self.bbw_rank_vol = float(r.get("bbw_rank_volatile", 70))
        self.ema_length = int(r.get("ema_length", 50))
        self.ema_slope_min = float(r.get("ema_slope_min", 0.5))

        self.orb_london = o.get("london_window", ["07:00", "08:00"])
        self.orb_ny = o.get("newyork_window", ["12:00", "13:00"])
        self.orb_min_consol = int(o.get("min_consolidation_candles", 3))
        self.orb_tolerance = float(o.get("retest_tolerance_atr", 0.15))
        self.orb_require_squeeze = bool(o.get("require_h1_squeeze", True))

        self.conf_base = int(c.get("base", 40))
        self.conf_entry = int(c.get("threshold_entry", 70))
        self.conf_watch = int(c.get("threshold_watchlist", 50))
        self.suppress_out_of_session = bool(sess.get("suppress_out_of_session", True))

    # ------------------------------------------------------------------
    def bias_h4(self, df_h4: pd.DataFrame) -> int:
        if len(df_h4) < max(60, self.bb_length + 10):
            return 0
        atr_h4 = float(atr(df_h4, self.atr_length).iloc[-1])
        state = analyze(
            df_h4,
            k=self.pivot_major,
            atr_value=atr_h4,
            displacement_mult=self.disp_mult,
        )
        if state.swing_high is None or state.swing_low is None:
            return 0

        score = 0
        if state.trend > 0:
            score += 1
        elif state.trend < 0:
            score -= 1

        span = state.swing_high - state.swing_low
        if span > 0:
            position = (float(df_h4["close"].iloc[-1]) - state.swing_low) / span
            score += 1 if position <= 0.5 else -1

        bb = add_bollinger(df_h4, self.bb_length, self.bb_mult)
        pct_b = float(bb["pct_b"].iloc[-1])
        if pct_b < 0.2:
            score += 1
        elif pct_b > 0.8:
            score -= 1

        score = max(-3, min(3, score))
        return score if abs(score) >= 2 else 0

    # ------------------------------------------------------------------
    def evaluate(
        self,
        df_m15: pd.DataFrame,
        df_h1: pd.DataFrame,
        df_h4: pd.DataFrame,
        macro_bias: int | None = None,
        blackout: bool = False,
        now: datetime | None = None,
    ) -> SignalEvent | None:
        if min(len(df_m15), len(df_h1), len(df_h4)) < 60:
            return None

        ts = pd.Timestamp(now) if now else df_m15.index[-1]
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")

        session = session_label(ts.to_pydatetime())
        if session == "break":
            return None
        if blackout:
            return None
        if self.suppress_out_of_session and not in_killzone(ts.to_pydatetime()):
            return None

        regime = classify(
            df_h1,
            adx_threshold=self.adx_threshold,
            atr_rank_volatile=self.atr_rank_vol,
            bbw_rank_volatile=self.bbw_rank_vol,
            ema_length=self.ema_length,
            ema_slope_min=self.ema_slope_min,
        )
        bias = self.bias_h4(df_h4)
        if bias == 0:
            return None

        atr15 = atr(df_m15, self.atr_length)
        event = None
        if self.setup_a:
            event = self._setup_a(df_m15, df_h1, bias, regime, atr15, session, ts)
        if event is None and self.setup_b:
            event = self._setup_b(df_m15, df_h1, bias, regime, atr15, session, ts)

        if event is None:
            return None
        if event.confidence < self.conf_watch:
            return None
        if macro_bias is not None and self._macro_conflict(event.side, macro_bias):
            return None
        return event

    # ------------------------------------------------------------------
    def _setup_a(self, df, df_h1, bias, regime, atr15, session, ts) -> SignalEvent | None:
        if regime == Regime.VOLATILE:
            return None

        bb1 = add_bollinger(df_h1, self.bb_length, self.bb_mult)
        if not is_squeeze(
            bb1, self.squeeze_lookback, int(self.squeeze_percentile), recent=self.squeeze_recent
        ):
            return None

        side = "long" if bias > 0 else "short"
        atr_value = float(atr15.iloc[-1])
        if atr_value <= 0:
            return None

        highs, lows = pivot_prices(df, k=3)
        levels = equal_levels(highs, lows, atr_value, self.equal_mult)
        if not levels:
            return None

        close = float(df["close"].iloc[-1])
        kind = "ssl" if side == "long" else "bsl"
        candidates = sorted(
            [lvl for lvl in levels if lvl.kind == kind],
            key=lambda lvl: abs(lvl.price - close),
        )[:4]

        atr20 = float(atr(df, 20).iloc[-1])
        atr_h1 = float(atr(df_h1, self.atr_length).iloc[-1])
        fvgs = find_fvgs(df, atr15, self.fvg_min_mult)
        blocks = find_order_blocks(df, atr15, self.disp_mult)

        for level in candidates:
            sweep_idx = find_sweep(
                df, level.price, side, atr_value, self.sweep_mult, lookback=self.sweep_lookback
            )
            if sweep_idx is None:
                continue
            if not displacement_after(df, sweep_idx, atr20, self.disp_mult):
                continue
            if not confirmation_after_sweep(
                df, sweep_idx, side, atr_value, self.disp_mult
            ):
                continue

            fvg = select_fvg(fvgs, side, close, self.fvg_max_fill)
            ob = select_order_block(blocks, side, close, self.ob_fresh_only)
            if fvg is None and ob is None:
                continue

            if fvg is not None and ob is not None:
                zone = (max(fvg.low, ob.low), min(fvg.high, ob.high))
                if zone[0] > zone[1]:
                    zone = (fvg.low, fvg.high)
            elif fvg is not None:
                zone = (fvg.low, fvg.high)
            else:
                zone = (ob.low, ob.high)

            entry = (zone[0] + zone[1]) / 2.0
            sweep_extreme = float(df["low"].iloc[sweep_idx]) if side == "long" else float(
                df["high"].iloc[sweep_idx]
            )
            if side == "long":
                stop_anchor = min(sweep_extreme, ob.low if ob else sweep_extreme)
                sl = stop_anchor - self.sl_pad * atr_value
                risk = entry - sl
                if risk <= 0:
                    continue
                tp1 = entry + self.tp1_mult * atr_h1
                tp2 = nearest_above([lvl.price for lvl in levels if lvl.kind == "bsl"], entry)
                if tp2 is None:
                    tp2 = float(bb1["bb_up"].iloc[-1])
            else:
                stop_anchor = max(sweep_extreme, ob.high if ob else sweep_extreme)
                sl = stop_anchor + self.sl_pad * atr_value
                risk = sl - entry
                if risk <= 0:
                    continue
                tp1 = entry - self.tp1_mult * atr_h1
                tp2 = nearest_below([lvl.price for lvl in levels if lvl.kind == "ssl"], entry)
                if tp2 is None:
                    tp2 = float(bb1["bb_lo"].iloc[-1])

            rr = abs(tp1 - entry) / risk
            if rr < self.min_rr:
                continue

            reasons = [
                f"bias_h4_{bias:+d}",
                f"regime_{regime.value.lower()}",
                f"h1_squeeze_p{int(self.squeeze_percentile)}",
                f"sweep_{level.price:.2f}",
                "internal_choch",
                "displacement",
            ]
            if fvg is not None:
                reasons.append(f"fvg_{fvg.size:.2f}")
            if ob is not None:
                reasons.append("fresh_ob")

            confidence = self._confidence(
                bias=bias,
                regime=regime,
                session=session,
                fvg=fvg,
                ob=ob,
                macro_bias=None,
            )
            return SignalEvent(
                symbol=self.symbol,
                setup="A",
                side=side,
                tf="15m",
                entry=entry,
                sl=sl,
                tp1=tp1,
                tp2=float(tp2),
                rr=rr,
                confidence=confidence,
                reasons=reasons,
                session=session,
                regime=regime.value,
                trigger_ts=ts,
            )
        return None

    # ------------------------------------------------------------------
    def _setup_b(self, df, df_h1, bias, regime, atr15, session, ts) -> SignalEvent | None:
        if regime != Regime.TRENDING:
            return None

        hour = ts.hour
        if 7 <= hour <= 10:
            start, end, name = self.orb_london[0], self.orb_london[1], "london"
        elif 12 <= hour <= 15:
            start, end, name = self.orb_ny[0], self.orb_ny[1], "newyork"
        else:
            return None

        rng = build_session_range(df, start, end, name, self.orb_min_consol)
        if rng is None:
            return None

        if self.orb_require_squeeze:
            bb1 = add_bollinger(df_h1, self.bb_length, self.bb_mult)
            if not is_squeeze(bb1, self.squeeze_lookback, int(self.squeeze_percentile), recent=10):
                return None

        atr_value = float(atr15.iloc[-1])
        side = breakout_side(df, rng, atr_value, self.orb_tolerance, self.orb_min_consol)
        if side is None:
            return None
        if (side == "long" and bias < 0) or (side == "short" and bias > 0):
            return None

        close = float(df["close"].iloc[-1])
        entry = close
        mid = (rng.high + rng.low) / 2.0
        if side == "long":
            sl = mid
            risk = entry - sl
            tp1 = entry + rng.size
            tp2 = entry + 1.5 * rng.size
        else:
            sl = mid
            risk = sl - entry
            tp1 = entry - rng.size
            tp2 = entry - 1.5 * rng.size

        if risk <= 0:
            return None
        rr = abs(tp1 - entry) / risk
        if rr < self.min_rr:
            return None

        confidence = self._confidence(
            bias=bias,
            regime=regime,
            session=session,
            fvg=None,
            ob=None,
            macro_bias=None,
        )
        return SignalEvent(
            symbol=self.symbol,
            setup="B",
            side=side,
            tf="15m",
            entry=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            rr=rr,
            confidence=confidence,
            reasons=[
                f"bias_h4_{bias:+d}",
                f"regime_{regime.value.lower()}",
                f"orb_{name}",
                f"range_{rng.low:.2f}-{rng.high:.2f}",
            ],
            session=session,
            regime=regime.value,
            trigger_ts=ts,
        )

    # ------------------------------------------------------------------
    def _confidence(
        self,
        bias: int,
        regime: Regime,
        session: str,
        fvg,
        ob,
        macro_bias: int | None,
    ) -> int:
        score = self.conf_base
        score += 20 if abs(bias) >= 3 else 12
        score += 8
        score += 12
        if fvg is not None:
            score += 8
        if ob is not None:
            score += 8
        if fvg is not None and ob is not None:
            score += 8
        if regime in {Regime.TRENDING, Regime.RANGING}:
            score += 8
        if session_score(session) >= 3:
            score += 5
        if macro_bias is not None:
            if (macro_bias > 0 and bias > 0) or (macro_bias < 0 and bias < 0):
                score += 8
        if fvg is not None and fvg.filled_pct > self.fvg_max_fill:
            score -= 10
        if regime == Regime.VOLATILE:
            score -= 10
        return max(0, min(100, score))

    @staticmethod
    def _macro_conflict(side: str, macro_bias: int) -> bool:
        if macro_bias >= 20 and side == "short":
            return True
        if macro_bias <= -20 and side == "long":
            return True
        return False
