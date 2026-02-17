"""
BacktestEngine — Event-Driven Backtesting with Realistic Slippage

Produces:
- Trade journal with MAE/MFE per trade
- Equity curve per timestep
- 17 performance metrics (Sharpe, Sortino, Calmar, ...)
- OHLC-aware slippage model

Design principles:
- All monetary values in Decimal (no float for prices/PnL)
- Reproducible with seed (same result bit-per-bit)
- Pluggable Strategy via ABC interface

Ref: FUSION_PLAN Fase 2, item 2.1
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Any
from loguru import logger

from src.quant.triple_barrier import (
    TripleBarrier,
    BarrierState,
    ExitSignal,
    ExitReason,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Trade:
    """A completed trade record."""
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str                  # 'LONG' | 'SHORT'
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal                   # Quantity
    pnl: Decimal                    # Absolute P&L after costs
    pnl_pct: float                  # P&L percentage
    commission_paid: Decimal
    slippage_cost: Decimal
    exit_reason: str                # ExitReason value
    max_favorable: Decimal          # Maximum Favorable Excursion
    max_adverse: Decimal            # Maximum Adverse Excursion
    duration_hours: float
    entry_tag: str = ""             # e.g. 'trend_buy', 'mean_rev_sell'


@dataclass
class BacktestMetrics:
    """All computed performance metrics."""
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0              # Percentage
    max_drawdown_duration: int = 0         # Bars
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    avg_trade_duration: float = 0.0        # Hours
    max_consecutive_losses: int = 0
    recovery_factor: float = 0.0
    annual_return: float = 0.0
    total_commission: Decimal = Decimal("0")
    total_slippage: Decimal = Decimal("0")


@dataclass
class BacktestResult:
    """Complete backtest output."""
    journal: List[Trade]
    equity_curve: np.ndarray
    metrics: BacktestMetrics
    daily_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))


@dataclass
class BacktestConfig:
    """Backtest parameters."""
    initial_capital: Decimal = Decimal("10000")
    commission_pct: Decimal = Decimal("0.001")     # 0.1% per side
    slippage_pct: float = 0.0001                   # 0.01% base slippage
    position_size_pct: float = 0.02                # 2% of equity per trade
    max_open_positions: int = 1
    # Triple barrier defaults
    sl_pct: float = 0.02
    tp_pct: float = 0.03
    max_bars: int = 48
    trailing: bool = False
    trailing_activation: float = 0.015
    trailing_delta: float = 0.01
    seed: int = 42


# =============================================================================
# STRATEGY INTERFACE
# =============================================================================

class Strategy(ABC):
    """
    Base class for all backtestable strategies.

    Implement `on_candle` to produce signals.
    """

    @abstractmethod
    def on_candle(
        self,
        idx: int,
        row: pd.Series,
        history: pd.DataFrame,
    ) -> Optional[Dict[str, Any]]:
        """
        Called for each new candle.

        Args:
            idx: Integer index into the DataFrame
            row: Current OHLCV row
            history: All data up to and including current bar

        Returns:
            None = no action
            {'direction': 'LONG'|'SHORT', 'tag': str} = open position
        """
        ...

    def on_trade_closed(self, trade: Trade) -> None:
        """Optional callback after a trade closes."""
        pass


# =============================================================================
# SLIPPAGE MODEL
# =============================================================================

def _apply_entry_slippage(
    price: Decimal, direction: int, base_slippage: float
) -> tuple[Decimal, Decimal]:
    """
    Entry slippage: fixed percentage.
    Returns (fill_price, slippage_cost_per_unit).
    """
    slip = Decimal(str(base_slippage))
    if direction == 1:  # LONG — buy higher
        fill = price * (1 + slip)
    else:  # SHORT — sell lower
        fill = price * (1 - slip)
    cost = abs(fill - price)
    return fill, cost


def _apply_exit_slippage_ohlc(
    target_price: Decimal,
    bar_open: Decimal,
    atr: Decimal,
    direction: int,
    exit_reason: ExitReason,
    base_slippage: float,
) -> Decimal:
    """
    OHLC-aware exit slippage (from freqtrade model).

    SL exits:
        If bar open already past SL → fill at bar open (gap)
        Else → fill at SL + 0.01% * ATR
    TP exits:
        If bar open already past TP → fill at bar open (favorable gap)
        Else → fill at TP - 0.01% * ATR
    """
    slip_atr = atr * Decimal(str(base_slippage))

    if exit_reason == ExitReason.STOP_LOSS:
        if direction == 1:
            # Long SL: price going down
            if bar_open <= target_price:
                return bar_open  # Gap down past SL
            return target_price - slip_atr
        else:
            # Short SL: price going up
            if bar_open >= target_price:
                return bar_open  # Gap up past SL
            return target_price + slip_atr

    elif exit_reason == ExitReason.TAKE_PROFIT:
        if direction == 1:
            if bar_open >= target_price:
                return bar_open  # Favorable gap
            return target_price - slip_atr
        else:
            if bar_open <= target_price:
                return bar_open
            return target_price + slip_atr

    # Trailing / time / signal: fill at close (no specific target)
    return target_price


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class BacktestEngine:
    """
    Event-driven backtesting engine.

    Usage:
        engine = BacktestEngine()
        result = engine.run(data, strategy, config)
        print(engine.format_report(result.metrics))
    """

    def run(
        self,
        data: pd.DataFrame,
        strategy: Strategy,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        """
        Run a full backtest.

        Args:
            data: DataFrame with columns [open, high, low, close, volume]
                  and a DatetimeIndex.
            strategy: Strategy instance implementing on_candle.
            config: Backtest configuration (uses defaults if None).

        Returns:
            BacktestResult with journal, equity curve, and metrics.
        """
        cfg = config or BacktestConfig()
        np.random.seed(cfg.seed)

        # Validate input
        required = {"open", "high", "low", "close"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Data missing columns: {missing}")
        if len(data) < 2:
            raise ValueError("Need at least 2 rows of data")

        # Precompute ATR for slippage model
        atr_series = self._compute_atr(data, period=14)

        # State
        equity = float(cfg.initial_capital)
        equity_curve = np.zeros(len(data))
        journal: List[Trade] = []
        open_positions: List[_OpenPosition] = []

        for i in range(len(data)):
            row = data.iloc[i]
            ts = data.index[i]

            bar_o = Decimal(str(row["open"]))
            bar_h = Decimal(str(row["high"]))
            bar_l = Decimal(str(row["low"]))
            bar_c = Decimal(str(row["close"]))
            atr_val = Decimal(str(max(atr_series[i], 1e-10)))

            # -- Check exits on open positions --
            closed_indices = []
            for pos_idx, pos in enumerate(open_positions):
                exit_sig = pos.barrier_mgr.check_exit(
                    pos.barrier_state, bar_o, bar_h, bar_l, bar_c, i
                )
                if exit_sig is not None:
                    # Apply OHLC slippage to the exit
                    fill_price = _apply_exit_slippage_ohlc(
                        exit_sig.exit_price, bar_o, atr_val,
                        pos.direction, exit_sig.reason, cfg.slippage_pct,
                    )
                    trade = self._close_position(pos, fill_price, ts, exit_sig, cfg, data, i)
                    journal.append(trade)
                    equity += float(trade.pnl)
                    strategy.on_trade_closed(trade)
                    closed_indices.append(pos_idx)

            # Remove closed positions (reverse order to keep indices valid)
            for idx in reversed(closed_indices):
                open_positions.pop(idx)

            # -- Check for new entry signals --
            if len(open_positions) < cfg.max_open_positions and i < len(data) - cfg.max_bars - 1:
                signal = strategy.on_candle(i, row, data.iloc[: i + 1])
                if signal is not None:
                    direction_str = signal.get("direction", "LONG")
                    direction = 1 if direction_str == "LONG" else -1
                    tag = signal.get("tag", "")

                    entry_price = bar_c  # Enter at close of signal bar
                    fill_price, slip_cost = _apply_entry_slippage(
                        entry_price, direction, cfg.slippage_pct
                    )

                    # Position sizing
                    risk_capital = Decimal(str(equity * cfg.position_size_pct))
                    size = (risk_capital / fill_price).quantize(
                        Decimal("0.00000001"), rounding=ROUND_HALF_UP
                    )
                    if size <= 0:
                        equity_curve[i] = equity
                        continue

                    commission = fill_price * size * cfg.commission_pct

                    # Create barrier state
                    tb = TripleBarrier(
                        sl_pct=cfg.sl_pct,
                        tp_pct=cfg.tp_pct,
                        max_bars=cfg.max_bars,
                        trailing=cfg.trailing,
                        trailing_activation=cfg.trailing_activation,
                        trailing_delta=cfg.trailing_delta,
                    )
                    barrier_state = tb.open_position(fill_price, direction, i)

                    pos = _OpenPosition(
                        entry_price=fill_price,
                        entry_time=ts,
                        direction=direction,
                        size=size,
                        entry_commission=commission,
                        entry_slippage=slip_cost * size,
                        barrier_mgr=tb,
                        barrier_state=barrier_state,
                        entry_tag=tag,
                        mfe=Decimal("0"),
                        mae=Decimal("0"),
                    )
                    open_positions.append(pos)

            # -- Update MAE/MFE for open positions --
            for pos in open_positions:
                unrealized = (bar_c - pos.entry_price) * pos.direction
                if unrealized > pos.mfe:
                    pos.mfe = unrealized
                if unrealized < -pos.mae:
                    pos.mae = abs(unrealized)

            equity_curve[i] = equity

        # Force-close any remaining positions at last bar
        if open_positions:
            last_row = data.iloc[-1]
            last_ts = data.index[-1]
            last_close = Decimal(str(last_row["close"]))
            for pos in open_positions:
                exit_sig = ExitSignal(
                    ExitReason.TIME_LIMIT, last_close, len(data) - 1, 0.0
                )
                trade = self._close_position(
                    pos, last_close, last_ts, exit_sig, cfg, data, len(data) - 1
                )
                journal.append(trade)
                equity += float(trade.pnl)

        equity_curve[-1] = equity

        # Compute metrics
        metrics = self._compute_metrics(journal, equity_curve, cfg)

        # Daily returns
        daily_ret = self._compute_daily_returns(equity_curve, data.index)

        return BacktestResult(
            journal=journal,
            equity_curve=equity_curve,
            metrics=metrics,
            daily_returns=daily_ret,
        )

    # -----------------------------------------------------------------
    # INTERNAL
    # -----------------------------------------------------------------

    @staticmethod
    def _close_position(
        pos: _OpenPosition,
        fill_price: Decimal,
        exit_time: pd.Timestamp,
        exit_sig: ExitSignal,
        cfg: BacktestConfig,
        data: pd.DataFrame,
        exit_idx: int,
    ) -> Trade:
        """Build a Trade record from a closed position."""
        exit_commission = fill_price * pos.size * cfg.commission_pct
        total_commission = pos.entry_commission + exit_commission

        if pos.direction == 1:
            gross_pnl = (fill_price - pos.entry_price) * pos.size
        else:
            gross_pnl = (pos.entry_price - fill_price) * pos.size

        net_pnl = gross_pnl - total_commission
        slippage_cost = pos.entry_slippage + abs(fill_price - exit_sig.exit_price) * pos.size

        pnl_pct = float(net_pnl / (pos.entry_price * pos.size)) if pos.size > 0 else 0.0

        duration_seconds = (exit_time - pos.entry_time).total_seconds()
        duration_hours = duration_seconds / 3600.0

        return Trade(
            entry_time=pos.entry_time,
            exit_time=exit_time,
            direction="LONG" if pos.direction == 1 else "SHORT",
            entry_price=pos.entry_price,
            exit_price=fill_price,
            size=pos.size,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            commission_paid=total_commission,
            slippage_cost=slippage_cost,
            exit_reason=exit_sig.reason.value,
            max_favorable=pos.mfe * pos.size,
            max_adverse=pos.mae * pos.size,
            duration_hours=duration_hours,
            entry_tag=pos.entry_tag,
        )

    @staticmethod
    def _compute_atr(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Compute ATR for slippage model."""
        high = data["high"].values.astype(float)
        low = data["low"].values.astype(float)
        close = data["close"].values.astype(float)

        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]

        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
        )

        atr = np.zeros_like(tr)
        atr[0] = tr[0]
        alpha = 2.0 / (period + 1)
        for i in range(1, len(tr)):
            atr[i] = alpha * tr[i] + (1 - alpha) * atr[i - 1]

        return atr

    @staticmethod
    def _compute_daily_returns(equity_curve: np.ndarray, index: pd.DatetimeIndex) -> pd.Series:
        """Compute daily returns from equity curve."""
        eq = pd.Series(equity_curve, index=index)
        daily = eq.resample("1D").last().dropna()
        returns = daily.pct_change().dropna()
        return returns

    @staticmethod
    def _compute_metrics(
        journal: List[Trade],
        equity_curve: np.ndarray,
        cfg: BacktestConfig,
    ) -> BacktestMetrics:
        """Compute all 17+ performance metrics."""
        m = BacktestMetrics()
        m.total_trades = len(journal)

        if m.total_trades == 0:
            return m

        # -- Basic trade stats --
        pnls = [float(t.pnl) for t in journal]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        m.win_rate = len(wins) / m.total_trades if m.total_trades > 0 else 0.0
        m.avg_win = float(np.mean(wins)) if wins else 0.0
        m.avg_loss = float(np.mean(losses)) if losses else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        m.expectancy = float(np.mean(pnls))

        # Long/short breakdown
        long_trades = [t for t in journal if t.direction == "LONG"]
        short_trades = [t for t in journal if t.direction == "SHORT"]
        long_wins = [t for t in long_trades if float(t.pnl) > 0]
        short_wins = [t for t in short_trades if float(t.pnl) > 0]
        m.long_win_rate = len(long_wins) / len(long_trades) if long_trades else 0.0
        m.short_win_rate = len(short_wins) / len(short_trades) if short_trades else 0.0

        # Duration
        m.avg_trade_duration = float(np.mean([t.duration_hours for t in journal]))

        # Commissions & slippage
        m.total_commission = sum((t.commission_paid for t in journal), Decimal("0"))
        m.total_slippage = sum((t.slippage_cost for t in journal), Decimal("0"))

        # -- Max consecutive losses --
        max_consec = 0
        current_consec = 0
        for p in pnls:
            if p <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0
        m.max_consecutive_losses = max_consec

        # -- Equity curve metrics --
        eq = equity_curve
        initial = float(cfg.initial_capital)

        # Drawdown
        running_max = np.maximum.accumulate(eq)
        drawdowns = (running_max - eq) / np.where(running_max > 0, running_max, 1)
        m.max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Max drawdown duration (in bars)
        in_dd = drawdowns > 0
        dd_duration = 0
        max_dd_dur = 0
        for v in in_dd:
            if v:
                dd_duration += 1
                max_dd_dur = max(max_dd_dur, dd_duration)
            else:
                dd_duration = 0
        m.max_drawdown_duration = max_dd_dur

        # Returns for ratio computation
        eq_returns = np.diff(eq) / np.where(eq[:-1] != 0, eq[:-1], 1)
        eq_returns = eq_returns[np.isfinite(eq_returns)]

        if len(eq_returns) > 1:
            mean_ret = np.mean(eq_returns)
            std_ret = np.std(eq_returns, ddof=1)
            downside = eq_returns[eq_returns < 0]
            downside_std = np.std(downside, ddof=1) if len(downside) > 1 else 1e-10

            # Annualization (assume ~252 trading days, data may be intraday)
            ann_factor = np.sqrt(252)

            # Sharpe
            m.sharpe_ratio = float((mean_ret / std_ret) * ann_factor) if std_ret > 0 else 0.0

            # Sortino
            m.sortino_ratio = float((mean_ret / downside_std) * ann_factor) if downside_std > 0 else 0.0

        # Annual return (simple CAGR proxy)
        total_return = (eq[-1] - initial) / initial if initial > 0 else 0.0
        n_bars = len(eq)
        if n_bars > 0 and total_return > -1:
            # Rough annualization based on bar count
            m.annual_return = total_return  # Will be refined with actual timeframe

        # Calmar
        m.calmar_ratio = m.annual_return / m.max_drawdown if m.max_drawdown > 0 else 0.0

        # Recovery factor
        m.recovery_factor = total_return / m.max_drawdown if m.max_drawdown > 0 else 0.0

        return m

    # -----------------------------------------------------------------
    # REPORTING
    # -----------------------------------------------------------------

    @staticmethod
    def format_report(metrics: BacktestMetrics) -> str:
        """Format metrics as a human-readable report."""
        lines = [
            "=" * 55,
            "           BACKTEST PERFORMANCE REPORT",
            "=" * 55,
            f"  Total Trades:           {metrics.total_trades}",
            f"  Win Rate:               {metrics.win_rate:.1%}",
            f"  Long Win Rate:          {metrics.long_win_rate:.1%}",
            f"  Short Win Rate:         {metrics.short_win_rate:.1%}",
            f"  Profit Factor:          {metrics.profit_factor:.2f}",
            f"  Expectancy:             {metrics.expectancy:.4f}",
            f"  Avg Win:                {metrics.avg_win:.4f}",
            f"  Avg Loss:               {metrics.avg_loss:.4f}",
            "-" * 55,
            f"  Sharpe Ratio:           {metrics.sharpe_ratio:.3f}",
            f"  Sortino Ratio:          {metrics.sortino_ratio:.3f}",
            f"  Calmar Ratio:           {metrics.calmar_ratio:.3f}",
            f"  Recovery Factor:        {metrics.recovery_factor:.3f}",
            f"  Annual Return:          {metrics.annual_return:.2%}",
            "-" * 55,
            f"  Max Drawdown:           {metrics.max_drawdown:.2%}",
            f"  Max DD Duration (bars): {metrics.max_drawdown_duration}",
            f"  Max Consec. Losses:     {metrics.max_consecutive_losses}",
            "-" * 55,
            f"  Avg Trade Duration (h): {metrics.avg_trade_duration:.1f}",
            f"  Total Commission:       {metrics.total_commission}",
            f"  Total Slippage:         {metrics.total_slippage}",
            "=" * 55,
        ]
        return "\n".join(lines)


# =============================================================================
# INTERNAL — OPEN POSITION TRACKER
# =============================================================================

@dataclass
class _OpenPosition:
    """Internal: tracks an open position during backtest."""
    entry_price: Decimal
    entry_time: pd.Timestamp
    direction: int                  # 1 or -1
    size: Decimal
    entry_commission: Decimal
    entry_slippage: Decimal
    barrier_mgr: TripleBarrier
    barrier_state: BarrierState
    entry_tag: str
    mfe: Decimal                    # Max favorable excursion (per unit)
    mae: Decimal                    # Max adverse excursion (per unit)


__all__ = [
    "Trade",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestConfig",
    "Strategy",
    "BacktestEngine",
]
