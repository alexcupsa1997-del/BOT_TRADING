"""
Breakout Strategy — Optimal for VOLATILE regime.

Entry conditions:
    1. BB squeeze release: bandwidth expands after contraction
    2. Volume surge: current volume > 2x 20-bar mean
    3. ATR expansion: current ATR > 1.5x 20-bar ATR mean
    4. Price breaks above/below recent range (20-bar high/low)

Direction determined by the side of the breakout.
SL: inside the previous range, TP: 2x ATR from entry.

Ref: FUSION_PLAN Fase 4, item 4.7
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy, StrategySignal


class Breakout(BaseStrategy):

    def __init__(self, squeeze_lookback: int = 20,
                 volume_surge_factor: float = 2.0,
                 atr_expansion_factor: float = 1.5,
                 min_conditions: int = 2):
        self.squeeze_lookback = squeeze_lookback
        self.volume_surge_factor = volume_surge_factor
        self.atr_expansion_factor = atr_expansion_factor
        self.min_conditions = min_conditions

    @property
    def name(self) -> str:
        return "breakout"

    @property
    def preferred_regime(self) -> str:
        return "VOLATILE"

    def on_candle(self, idx: int, row: pd.Series,
                  history: pd.DataFrame) -> Optional[StrategySignal]:
        lb = self.squeeze_lookback
        if len(history) < lb + 5:
            return None

        close = row.get("close", 0)
        atr = row.get("atr", 0)
        bb_bandwidth = row.get("bb_bandwidth", None)

        if pd.isna(close) or pd.isna(atr) or close == 0:
            return None

        recent = history.iloc[-(lb + 1):-1]

        # ── Condition 1: BB squeeze release ──
        squeeze_release = False
        if bb_bandwidth is not None and not pd.isna(bb_bandwidth):
            if "bb_bandwidth" in recent.columns:
                prev_bw = recent["bb_bandwidth"].mean()
                if prev_bw > 0:
                    squeeze_release = bb_bandwidth > 1.3 * prev_bw

        # ── Condition 2: Volume surge ──
        vol_surge = False
        if "volume" in history.columns:
            vol_mean = recent["volume"].mean()
            vol_current = row.get("volume", 0)
            if vol_mean > 0:
                vol_surge = vol_current > self.volume_surge_factor * vol_mean

        # ── Condition 3: ATR expansion ──
        atr_expand = False
        if "atr" in recent.columns:
            atr_mean = recent["atr"].mean()
            if atr_mean > 0:
                atr_expand = atr > self.atr_expansion_factor * atr_mean

        # ── Condition 4: Price breaks range ──
        range_high = recent["high"].max() if "high" in recent.columns else close
        range_low = recent["low"].min() if "low" in recent.columns else close

        breakout_bull = close > range_high
        breakout_bear = close < range_low

        # Count conditions for direction
        if breakout_bull:
            conditions = sum([squeeze_release, vol_surge, atr_expand, True])
            if conditions >= self.min_conditions:
                return StrategySignal(
                    direction="LONG",
                    tag="breakout_long",
                    strength=conditions / 4.0,
                    metadata={
                        "range_high": range_high, "atr": atr,
                        "conditions": conditions,
                    },
                )

        if breakout_bear:
            conditions = sum([squeeze_release, vol_surge, atr_expand, True])
            if conditions >= self.min_conditions:
                return StrategySignal(
                    direction="SHORT",
                    tag="breakout_short",
                    strength=conditions / 4.0,
                    metadata={
                        "range_low": range_low, "atr": atr,
                        "conditions": conditions,
                    },
                )

        return None
