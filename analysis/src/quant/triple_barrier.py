"""
Triple Barrier Method — Labeling + Exit Management

Dual-use module:
1. LABELING: Generate trade labels (+1, -1, 0) for ML training
2. EXIT MANAGEMENT: Check exit conditions for backtest/live positions

Inspired by Marcos Lopez de Prado's Advances in Financial Machine Learning
and hummingbot Triple Barrier implementation.

Ref: FUSION_PLAN Fase 2, item 2.2
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from loguru import logger


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class ExitReason(str, Enum):
    """Why a position was closed."""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_LIMIT = "TIME_LIMIT"
    SIGNAL = "SIGNAL"


@dataclass
class BarrierConfig:
    """Configuration for triple barrier."""
    sl_pct: float = 0.02         # 2% stop loss
    tp_pct: float = 0.03         # 3% take profit
    max_bars: int = 48           # Max holding period in bars
    trailing: bool = False       # Enable trailing stop
    trailing_activation: float = 0.015  # Activate trailing after +1.5%
    trailing_delta: float = 0.01 # Trailing stop distance from peak


@dataclass
class ExitSignal:
    """Signal that a position should be closed."""
    reason: ExitReason
    exit_price: Decimal
    bar_index: int               # Which bar triggered the exit
    pnl_pct: float               # Estimated P&L percentage


@dataclass
class BarrierState:
    """Mutable state for tracking an open position's barriers."""
    entry_price: Decimal
    direction: int               # 1=LONG, -1=SHORT
    sl_level: Decimal
    tp_level: Decimal
    entry_bar: int
    max_bars: int
    trailing: bool
    trailing_activation: Decimal
    trailing_delta: float
    # Mutable tracking
    peak_price: Decimal = Decimal("0")
    trailing_active: bool = False
    trailing_sl: Decimal = Decimal("0")
    bars_held: int = 0


# =============================================================================
# TRIPLE BARRIER — CORE
# =============================================================================

class TripleBarrier:
    """
    Triple Barrier Method for labeling and exit management.

    Usage 1 — Labeling for ML training:
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        labels = tb.label_series(data)

    Usage 2 — Exit management in backtest/live:
        state = tb.open_position(entry_price, direction='LONG', bar_idx=0)
        exit_signal = tb.check_exit(state, current_candle)
    """

    def __init__(
        self,
        sl_pct: float = 0.02,
        tp_pct: float = 0.03,
        max_bars: int = 48,
        trailing: bool = False,
        trailing_activation: float = 0.015,
        trailing_delta: float = 0.01,
    ):
        self.config = BarrierConfig(
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            max_bars=max_bars,
            trailing=trailing,
            trailing_activation=trailing_activation,
            trailing_delta=trailing_delta,
        )

    # -----------------------------------------------------------------
    # USE 1: LABELING (for ML training)
    # -----------------------------------------------------------------

    def label_series(
        self,
        df: pd.DataFrame,
        close_col: str = "close",
        high_col: str = "high",
        low_col: str = "low",
        side: int = 1,
    ) -> pd.Series:
        """
        Label every bar in the DataFrame using triple barrier.

        Args:
            df: DataFrame with OHLC data
            close_col: Column name for close prices
            high_col: Column name for high prices
            low_col: Column name for low prices
            side: Trade direction (1=long, -1=short)

        Returns:
            Series of labels: +1 (TP hit), -1 (SL hit), 0 (timeout)
        """
        close = df[close_col].values
        high = df[high_col].values
        low = df[low_col].values
        n = len(close)

        labels = np.full(n, np.nan)
        sl_pct = self.config.sl_pct
        tp_pct = self.config.tp_pct
        max_bars = self.config.max_bars

        for i in range(n - 1):
            entry = close[i]
            if entry <= 0:
                continue

            if side == 1:
                tp_level = entry * (1 + tp_pct)
                sl_level = entry * (1 - sl_pct)
            else:
                tp_level = entry * (1 - tp_pct)
                sl_level = entry * (1 + sl_pct)

            label = 0  # default: timeout
            end = min(i + max_bars + 1, n)

            for j in range(i + 1, end):
                bar_high = high[j]
                bar_low = low[j]

                # Priority: SL checked first (safety)
                if side == 1:
                    if bar_low <= sl_level:
                        label = -1
                        break
                    if bar_high >= tp_level:
                        label = 1
                        break
                else:
                    if bar_high >= sl_level:
                        label = -1
                        break
                    if bar_low <= tp_level:
                        label = 1
                        break

            labels[i] = label

        return pd.Series(labels, index=df.index, name="tb_label")

    def label_series_detailed(
        self,
        df: pd.DataFrame,
        close_col: str = "close",
        high_col: str = "high",
        low_col: str = "low",
        side: int = 1,
    ) -> pd.DataFrame:
        """
        Like label_series but returns full barrier info.

        Returns DataFrame with columns:
            label, barrier_type, first_touch_bar, return_pct
        """
        close = df[close_col].values
        high = df[high_col].values
        low = df[low_col].values
        n = len(close)

        result = np.full((n, 4), np.nan)  # label, barrier_type_code, touch_bar, return
        sl_pct = self.config.sl_pct
        tp_pct = self.config.tp_pct
        max_bars = self.config.max_bars

        for i in range(n - 1):
            entry = close[i]
            if entry <= 0:
                continue

            if side == 1:
                tp_level = entry * (1 + tp_pct)
                sl_level = entry * (1 - sl_pct)
            else:
                tp_level = entry * (1 - tp_pct)
                sl_level = entry * (1 + sl_pct)

            label = 0
            barrier_code = 0  # 0=TIME, 1=TP, -1=SL
            touch_bar = max_bars
            end = min(i + max_bars + 1, n)

            for j in range(i + 1, end):
                bar_high = high[j]
                bar_low = low[j]

                if side == 1:
                    if bar_low <= sl_level:
                        label, barrier_code, touch_bar = -1, -1, j - i
                        break
                    if bar_high >= tp_level:
                        label, barrier_code, touch_bar = 1, 1, j - i
                        break
                else:
                    if bar_high >= sl_level:
                        label, barrier_code, touch_bar = -1, -1, j - i
                        break
                    if bar_low <= tp_level:
                        label, barrier_code, touch_bar = 1, 1, j - i
                        break

            exit_idx = min(i + touch_bar, n - 1)
            ret = (close[exit_idx] - entry) / entry * side
            result[i] = [label, barrier_code, touch_bar, ret]

        out = pd.DataFrame(
            result,
            index=df.index,
            columns=["label", "barrier_type", "first_touch_bar", "return_pct"],
        )
        return out

    # -----------------------------------------------------------------
    # USE 2: EXIT MANAGEMENT (for backtest / live)
    # -----------------------------------------------------------------

    def open_position(
        self,
        entry_price: Decimal,
        direction: int,
        bar_idx: int = 0,
    ) -> BarrierState:
        """
        Create a BarrierState for a new position.

        Args:
            entry_price: Entry price (Decimal)
            direction: 1=LONG, -1=SHORT
            bar_idx: Current bar index

        Returns:
            BarrierState ready for check_exit calls
        """
        ep = entry_price
        if direction == 1:
            sl = ep * (1 - Decimal(str(self.config.sl_pct)))
            tp = ep * (1 + Decimal(str(self.config.tp_pct)))
            activation = ep * (1 + Decimal(str(self.config.trailing_activation)))
        else:
            sl = ep * (1 + Decimal(str(self.config.sl_pct)))
            tp = ep * (1 - Decimal(str(self.config.tp_pct)))
            activation = ep * (1 - Decimal(str(self.config.trailing_activation)))

        return BarrierState(
            entry_price=ep,
            direction=direction,
            sl_level=sl,
            tp_level=tp,
            entry_bar=bar_idx,
            max_bars=self.config.max_bars,
            trailing=self.config.trailing,
            trailing_activation=activation,
            trailing_delta=self.config.trailing_delta,
            peak_price=ep,
        )

    def check_exit(
        self,
        state: BarrierState,
        bar_open: Decimal,
        bar_high: Decimal,
        bar_low: Decimal,
        bar_close: Decimal,
        bar_idx: int,
    ) -> Optional[ExitSignal]:
        """
        Check if a position should exit on this bar.

        Priority: STOP_LOSS > TAKE_PROFIT > TRAILING_STOP > TIME_LIMIT

        Args:
            state: Current barrier state
            bar_open/high/low/close: Current candle OHLC (Decimal)
            bar_idx: Current bar index

        Returns:
            ExitSignal if exit triggered, None otherwise
        """
        state.bars_held = bar_idx - state.entry_bar
        ep = state.entry_price
        d = state.direction

        # -- Update peak price for trailing --
        if state.trailing:
            if d == 1:
                if bar_high > state.peak_price:
                    state.peak_price = bar_high
                # Activate trailing
                if not state.trailing_active and bar_high >= state.trailing_activation:
                    state.trailing_active = True
                # Update trailing SL
                if state.trailing_active:
                    new_tsl = state.peak_price * (1 - Decimal(str(state.trailing_delta)))
                    if new_tsl > state.trailing_sl:
                        state.trailing_sl = new_tsl
            else:
                if bar_low < state.peak_price or state.peak_price == ep:
                    state.peak_price = bar_low
                if not state.trailing_active and bar_low <= state.trailing_activation:
                    state.trailing_active = True
                if state.trailing_active:
                    new_tsl = state.peak_price * (1 + Decimal(str(state.trailing_delta)))
                    if state.trailing_sl == 0 or new_tsl < state.trailing_sl:
                        state.trailing_sl = new_tsl

        # -- 1. STOP LOSS (highest priority) --
        if d == 1 and bar_low <= state.sl_level:
            # Gap down: fill at open if open already below SL
            fill = min(bar_open, state.sl_level) if bar_open <= state.sl_level else state.sl_level
            pnl = float((fill - ep) / ep) * d
            return ExitSignal(ExitReason.STOP_LOSS, fill, bar_idx, pnl)

        if d == -1 and bar_high >= state.sl_level:
            fill = max(bar_open, state.sl_level) if bar_open >= state.sl_level else state.sl_level
            pnl = float((ep - fill) / ep)
            return ExitSignal(ExitReason.STOP_LOSS, fill, bar_idx, pnl)

        # -- 2. TAKE PROFIT --
        if d == 1 and bar_high >= state.tp_level:
            fill = max(bar_open, state.tp_level) if bar_open >= state.tp_level else state.tp_level
            pnl = float((fill - ep) / ep) * d
            return ExitSignal(ExitReason.TAKE_PROFIT, fill, bar_idx, pnl)

        if d == -1 and bar_low <= state.tp_level:
            fill = min(bar_open, state.tp_level) if bar_open <= state.tp_level else state.tp_level
            pnl = float((ep - fill) / ep)
            return ExitSignal(ExitReason.TAKE_PROFIT, fill, bar_idx, pnl)

        # -- 3. TRAILING STOP --
        if state.trailing and state.trailing_active:
            if d == 1 and bar_low <= state.trailing_sl:
                fill = min(bar_open, state.trailing_sl) if bar_open <= state.trailing_sl else state.trailing_sl
                pnl = float((fill - ep) / ep) * d
                return ExitSignal(ExitReason.TRAILING_STOP, fill, bar_idx, pnl)
            if d == -1 and bar_high >= state.trailing_sl:
                fill = max(bar_open, state.trailing_sl) if bar_open >= state.trailing_sl else state.trailing_sl
                pnl = float((ep - fill) / ep)
                return ExitSignal(ExitReason.TRAILING_STOP, fill, bar_idx, pnl)

        # -- 4. TIME LIMIT --
        if state.bars_held >= state.max_bars:
            fill = bar_close
            pnl = float((fill - ep) / ep) * d
            return ExitSignal(ExitReason.TIME_LIMIT, fill, bar_idx, pnl)

        return None


__all__ = [
    "ExitReason",
    "BarrierConfig",
    "ExitSignal",
    "BarrierState",
    "TripleBarrier",
]
