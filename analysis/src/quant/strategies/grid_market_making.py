"""
Grid Market Making Strategy — Optimal for LOW_VOL regime.

Places a grid of virtual buy/sell orders around the current price
to capture the spread in low-volatility, ranging markets.

Grid logic:
    - N levels above and below mid price, spaced by `grid_spacing_pct`
    - BUY signals when price drops to a grid level below mid
    - SELL signals when price rises to a grid level above mid
    - Each level only triggers once until reset (price returns to mid)

Inspired by hummingbot's Pure Market Making strategy.
Uses Triple Barrier for position management.

Ref: FUSION_PLAN Fase 4, item 4.8
"""

from __future__ import annotations

from typing import Optional, Set

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy, StrategySignal


class GridMarketMaking(BaseStrategy):

    def __init__(self, n_levels: int = 3, grid_spacing_pct: float = 0.005,
                 adx_max: float = 18.0, recenter_bars: int = 50):
        """
        Args:
            n_levels: Number of grid levels above and below mid price.
            grid_spacing_pct: Spacing between levels as fraction of price.
            adx_max: Maximum ADX to confirm low-volatility environment.
            recenter_bars: Re-center grid every N bars.
        """
        self.n_levels = n_levels
        self.grid_spacing_pct = grid_spacing_pct
        self.adx_max = adx_max
        self.recenter_bars = recenter_bars

        self._mid_price: float = 0.0
        self._buy_levels: list[float] = []
        self._sell_levels: list[float] = []
        self._triggered_buys: Set[int] = set()
        self._triggered_sells: Set[int] = set()
        self._bars_since_center: int = 0

    @property
    def name(self) -> str:
        return "grid_market_making"

    @property
    def preferred_regime(self) -> str:
        return "LOW_VOL"

    def reset(self) -> None:
        self._mid_price = 0.0
        self._buy_levels = []
        self._sell_levels = []
        self._triggered_buys = set()
        self._triggered_sells = set()
        self._bars_since_center = 0

    def _recenter_grid(self, price: float) -> None:
        """Recalculate grid levels around current price."""
        self._mid_price = price
        spacing = price * self.grid_spacing_pct

        self._buy_levels = [price - spacing * (i + 1) for i in range(self.n_levels)]
        self._sell_levels = [price + spacing * (i + 1) for i in range(self.n_levels)]
        self._triggered_buys = set()
        self._triggered_sells = set()
        self._bars_since_center = 0

    def on_candle(self, idx: int, row: pd.Series,
                  history: pd.DataFrame) -> Optional[StrategySignal]:
        if len(history) < 30:
            return None

        close = row.get("close", 0)
        low = row.get("low", close)
        high = row.get("high", close)
        adx = row.get("adx", 25)

        if pd.isna(close) or close == 0:
            return None

        # Only trade in low-volatility environment
        if not pd.isna(adx) and adx > self.adx_max:
            return None

        # Initialize or re-center grid
        if self._mid_price == 0 or self._bars_since_center >= self.recenter_bars:
            self._recenter_grid(close)
            return None

        self._bars_since_center += 1

        # ── Check BUY levels (price dropped to grid level) ──
        for i, level in enumerate(self._buy_levels):
            if i not in self._triggered_buys and low <= level:
                self._triggered_buys.add(i)
                strength = (self.n_levels - i) / self.n_levels  # closer = stronger
                return StrategySignal(
                    direction="LONG",
                    tag=f"grid_buy_L{i + 1}",
                    strength=strength,
                    metadata={
                        "grid_level": level,
                        "mid_price": self._mid_price,
                        "level_idx": i + 1,
                    },
                )

        # ── Check SELL levels (price rose to grid level) ──
        for i, level in enumerate(self._sell_levels):
            if i not in self._triggered_sells and high >= level:
                self._triggered_sells.add(i)
                strength = (self.n_levels - i) / self.n_levels
                return StrategySignal(
                    direction="SHORT",
                    tag=f"grid_sell_L{i + 1}",
                    strength=strength,
                    metadata={
                        "grid_level": level,
                        "mid_price": self._mid_price,
                        "level_idx": i + 1,
                    },
                )

        return None
