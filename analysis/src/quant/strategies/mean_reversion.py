"""
Mean Reversion Strategy — Optimal for RANGING regime.

Entry LONG:
    1. Price touches/breaks BB lower band
    2. RSI < 30 (oversold)
    3. ADX < 20 (confirms ranging, no strong trend)
    4. Stochastic %K < 20 (confirms oversold)
    5. CCI < -100 (extreme reading)
    Signal: BUY if at least 3/5 conditions true

Entry SHORT: opposite conditions

Exit: TP at BB middle (mean reversion target), SL tight (1.5x ATR)
No trailing: target is fixed (mean reversion has no trend to follow)

Ref: FUSION_PLAN Fase 4, item 4.6
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .base_strategy import BaseStrategy, StrategySignal


class MeanReversion(BaseStrategy):

    def __init__(self, rsi_oversold: float = 30.0, rsi_overbought: float = 70.0,
                 adx_max: float = 20.0, stoch_oversold: float = 20.0,
                 stoch_overbought: float = 80.0, cci_extreme: float = 100.0,
                 min_conditions: int = 3):
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.adx_max = adx_max
        self.stoch_oversold = stoch_oversold
        self.stoch_overbought = stoch_overbought
        self.cci_extreme = cci_extreme
        self.min_conditions = min_conditions

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def preferred_regime(self) -> str:
        return "RANGING"

    def on_candle(self, idx: int, row: pd.Series,
                  history: pd.DataFrame) -> Optional[StrategySignal]:
        if len(history) < 30:
            return None

        close = row.get("close", 0)
        rsi = row.get("rsi", 50)
        adx = row.get("adx", 25)
        stoch_k = row.get("stoch_k", 50)
        cci = row.get("cci", 0)
        bb_lower = row.get("bb_lower", close)
        bb_upper = row.get("bb_upper", close)
        bb_middle = row.get("bb_middle", close)

        if any(pd.isna(v) for v in [close, rsi, adx]):
            return None

        # ── LONG conditions (oversold bounce) ──
        long_conditions = 0
        if close <= bb_lower:
            long_conditions += 1
        if rsi < self.rsi_oversold:
            long_conditions += 1
        if adx < self.adx_max:
            long_conditions += 1
        if not pd.isna(stoch_k) and stoch_k < self.stoch_oversold:
            long_conditions += 1
        if not pd.isna(cci) and cci < -self.cci_extreme:
            long_conditions += 1

        if long_conditions >= self.min_conditions:
            strength = long_conditions / 5.0
            return StrategySignal(
                direction="LONG",
                tag="mean_rev_long",
                strength=strength,
                metadata={
                    "rsi": rsi, "adx": adx, "stoch_k": stoch_k,
                    "bb_target": bb_middle, "conditions": long_conditions,
                },
            )

        # ── SHORT conditions (overbought rejection) ──
        short_conditions = 0
        if close >= bb_upper:
            short_conditions += 1
        if rsi > self.rsi_overbought:
            short_conditions += 1
        if adx < self.adx_max:
            short_conditions += 1
        if not pd.isna(stoch_k) and stoch_k > self.stoch_overbought:
            short_conditions += 1
        if not pd.isna(cci) and cci > self.cci_extreme:
            short_conditions += 1

        if short_conditions >= self.min_conditions:
            strength = short_conditions / 5.0
            return StrategySignal(
                direction="SHORT",
                tag="mean_rev_short",
                strength=strength,
                metadata={
                    "rsi": rsi, "adx": adx, "stoch_k": stoch_k,
                    "bb_target": bb_middle, "conditions": short_conditions,
                },
            )

        return None
