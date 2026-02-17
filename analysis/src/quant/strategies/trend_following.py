"""
Trend Following Strategy — Optimal for TRENDING regime.

Entry LONG:
    1. EMA ribbon aligned (9 > 21 > 50 > 200)
    2. ADX > 25 (trend confirmed)
    3. RSI > 50 AND < 70 (momentum positive, not overbought)
    4. MACD histogram positive (momentum confirmation)
    5. Volume > 1.2x mean (volume confirmation)
    Signal: weighted average of 5 filters, BUY if >= 3 passing

Entry SHORT: opposite conditions

Exit: Triple Barrier (ATR-based SL, R:R TP) + trailing stop

Ref: FUSION_PLAN Fase 4, item 4.5
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy, StrategySignal


class TrendFollowing(BaseStrategy):

    def __init__(self, adx_threshold: float = 25.0,
                 rsi_low: float = 50.0, rsi_high: float = 70.0,
                 volume_factor: float = 1.2, min_conditions: int = 3):
        self.adx_threshold = adx_threshold
        self.rsi_low = rsi_low
        self.rsi_high = rsi_high
        self.volume_factor = volume_factor
        self.min_conditions = min_conditions

    @property
    def name(self) -> str:
        return "trend_following"

    @property
    def preferred_regime(self) -> str:
        return "TRENDING"

    def on_candle(self, idx: int, row: pd.Series,
                  history: pd.DataFrame) -> Optional[StrategySignal]:
        if len(history) < 50:
            return None

        # Gather indicator values
        adx = row.get("adx", 0)
        rsi = row.get("rsi", 50)
        macd_hist = row.get("macd_hist", 0)
        close = row.get("close", 0)

        if any(pd.isna(v) for v in [adx, rsi, macd_hist, close]):
            return None

        # EMA values
        ema_9 = row.get("ema_9", close)
        ema_21 = row.get("ema_21", close)
        ema_50 = row.get("ema_50", close)
        ema_200 = row.get("ema_200", close)

        # Volume check
        if "volume" in history.columns:
            vol_mean = history["volume"].iloc[-20:].mean()
            vol_current = row.get("volume", vol_mean)
            vol_ok = vol_current > self.volume_factor * vol_mean if vol_mean > 0 else False
        else:
            vol_ok = True  # skip if no volume data

        # ── LONG conditions ──
        long_conditions = 0
        ema_bull = (ema_9 > ema_21 > ema_50) if not any(
            pd.isna(v) for v in [ema_9, ema_21, ema_50]) else False
        if ema_bull:
            long_conditions += 1
        if adx > self.adx_threshold:
            long_conditions += 1
        if self.rsi_low < rsi < self.rsi_high:
            long_conditions += 1
        if macd_hist > 0:
            long_conditions += 1
        if vol_ok:
            long_conditions += 1

        if long_conditions >= self.min_conditions:
            strength = long_conditions / 5.0
            return StrategySignal(
                direction="LONG",
                tag="trend_follow_long",
                strength=strength,
                metadata={"adx": adx, "rsi": rsi, "conditions": long_conditions},
            )

        # ── SHORT conditions ──
        short_conditions = 0
        ema_bear = (ema_9 < ema_21 < ema_50) if not any(
            pd.isna(v) for v in [ema_9, ema_21, ema_50]) else False
        if ema_bear:
            short_conditions += 1
        if adx > self.adx_threshold:
            short_conditions += 1
        rsi_short_low = 100 - self.rsi_high  # 30
        rsi_short_high = 100 - self.rsi_low   # 50
        if rsi_short_low < rsi < rsi_short_high:
            short_conditions += 1
        if macd_hist < 0:
            short_conditions += 1
        if vol_ok:
            short_conditions += 1

        if short_conditions >= self.min_conditions:
            strength = short_conditions / 5.0
            return StrategySignal(
                direction="SHORT",
                tag="trend_follow_short",
                strength=strength,
                metadata={"adx": adx, "rsi": rsi, "conditions": short_conditions},
            )

        return None
