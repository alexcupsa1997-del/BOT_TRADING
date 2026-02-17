"""
Paper Trading Harness — Continuous trading loop connecting
Orchestrator -> RiskManager -> ExchangeManager.

Single-symbol, async, with failsafe and circuit breaker.
Reuses TripleBarrier for exit management and BacktestEngine.Trade
for trade records.

Ref: FUSION_PLAN Fase 6
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

import pandas as pd
from loguru import logger

from src.quant.backtest_engine import Trade
from src.quant.triple_barrier import (
    TripleBarrier, BarrierState, ExitSignal,
)
from src.quant.risk_manager import RiskCalculator, RiskConfig
from src.ml.decision.fallback import FallbackDecision
from src.integration.notifier import Notifier, NotifyLevel


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class PaperTradingConfig:
    """Configuration for the paper trading harness."""
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    goliath_timeframe: str = "H1"
    poll_interval_seconds: float = 60.0
    min_confidence: float = 0.65
    initial_balance: Decimal = Decimal("10000")
    max_drawdown_pct: float = 0.15
    daily_loss_limit_pct: float = 0.05
    max_open_positions: int = 1
    # Triple barrier
    sl_pct: float = 0.02
    tp_pct: float = 0.03
    max_hold_bars: int = 48
    trailing: bool = False
    trailing_activation: float = 0.015
    trailing_delta: float = 0.01
    # Circuit breaker
    circuit_breaker_pct: float = 0.10
    circuit_breaker_window: int = 5
    # Failsafe
    max_consecutive_errors: int = 5
    # Reporting
    report_interval_hours: int = 24


# =============================================================================
# LIVE POSITION — Mutable In-Flight Tracker
# =============================================================================

@dataclass
class LivePosition:
    """Tracks a single open position until it closes."""
    trade_id: str
    symbol: str
    direction: str                          # "LONG" | "SHORT"
    entry_price: Decimal
    entry_time: datetime
    size: Decimal
    order_id: str
    barrier_state: BarrierState
    current_price: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    mae: Decimal = Decimal("0")
    mfe: Decimal = Decimal("0")
    bars_since_entry: int = 0

    def update_price(self, price: Decimal) -> None:
        """Update running P&L and MAE/MFE."""
        self.current_price = price
        direction_mult = 1 if self.direction == "LONG" else -1
        self.unrealized_pnl = (price - self.entry_price) * self.size * direction_mult

        excursion = float(price - self.entry_price) * direction_mult
        if excursion > float(self.mfe):
            self.mfe = Decimal(str(abs(excursion)))
        if excursion < 0 and abs(excursion) > float(self.mae):
            self.mae = Decimal(str(abs(excursion)))

    def to_trade(self, exit_price: Decimal, exit_time: datetime,
                 exit_reason: str) -> Trade:
        """Convert to a completed Trade record (reuses BacktestEngine.Trade)."""
        direction_mult = 1 if self.direction == "LONG" else -1
        pnl = (exit_price - self.entry_price) * self.size * direction_mult
        entry_f = float(self.entry_price)
        pnl_pct = (float(exit_price) - entry_f) / entry_f * direction_mult if entry_f > 0 else 0.0
        duration = (exit_time - self.entry_time).total_seconds() / 3600.0

        return Trade(
            entry_time=pd.Timestamp(self.entry_time),
            exit_time=pd.Timestamp(exit_time),
            direction=self.direction,
            entry_price=self.entry_price,
            exit_price=exit_price,
            size=self.size,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission_paid=Decimal("0"),
            slippage_cost=Decimal("0"),
            exit_reason=exit_reason,
            max_favorable=self.mfe * self.size,
            max_adverse=self.mae * self.size,
            duration_hours=duration,
            entry_tag="paper_live",
        )


# =============================================================================
# EQUITY TRACKER — Running Equity + Drawdown
# =============================================================================

@dataclass
class EquityTracker:
    """Tracks equity curve, peak, drawdown in real time."""
    initial_balance: Decimal
    current_balance: Decimal = Decimal("0")
    peak_balance: Decimal = Decimal("0")
    daily_start_balance: Decimal = Decimal("0")
    equity_snapshots: List[tuple] = field(default_factory=list)
    last_daily_reset: Optional[datetime] = None

    def __post_init__(self):
        if self.current_balance == 0:
            self.current_balance = self.initial_balance
        if self.peak_balance == 0:
            self.peak_balance = self.initial_balance
        if self.daily_start_balance == 0:
            self.daily_start_balance = self.initial_balance
        if self.last_daily_reset is None:
            self.last_daily_reset = datetime.now(timezone.utc)

    def record_trade(self, pnl: Decimal) -> None:
        """Update balance after a trade closes."""
        self.current_balance += pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        self.equity_snapshots.append(
            (datetime.now(timezone.utc).isoformat(), float(self.current_balance))
        )

    @property
    def drawdown_pct(self) -> float:
        """Current drawdown from peak as a fraction."""
        if self.peak_balance <= 0:
            return 0.0
        return float((self.peak_balance - self.current_balance) / self.peak_balance)

    @property
    def daily_pnl_pct(self) -> float:
        """Daily P&L as a fraction of daily start balance."""
        if self.daily_start_balance <= 0:
            return 0.0
        return float(
            (self.current_balance - self.daily_start_balance) / self.daily_start_balance
        )

    def reset_daily(self) -> None:
        """Reset daily tracking at the start of a new trading day."""
        self.daily_start_balance = self.current_balance
        self.last_daily_reset = datetime.now(timezone.utc)

    def should_halt_drawdown(self, max_dd: float) -> bool:
        """Check if drawdown exceeds maximum allowed."""
        return self.drawdown_pct >= max_dd

    def should_halt_daily(self, max_daily: float) -> bool:
        """Check if daily loss exceeds limit."""
        return self.daily_pnl_pct <= -max_daily


# =============================================================================
# PAPER TRADING HARNESS — Main Loop
# =============================================================================

class PaperTradingHarness:
    """
    Continuous paper trading loop.

    Lifecycle per tick:
    1. Fetch OHLCV from exchange
    2. Run orchestrator.analyze() -> FallbackDecision
    3. Check risk manager -> can_open_trade()
    4. If actionable signal: exchange.create_order()
    5. Monitor open position: check SL/TP/time via TripleBarrier
    6. On exit: close position, record trade, update equity, notify
    7. Check circuit breaker + failsafe
    8. Repeat
    """

    def __init__(
        self,
        config: PaperTradingConfig,
        exchange,           # ExchangeManager (async)
        orchestrator,       # TradingOrchestrator
        notifier: Notifier,
        risk_config: Optional[RiskConfig] = None,
    ):
        self.cfg = config
        self.exchange = exchange
        self.orchestrator = orchestrator
        self.notifier = notifier

        self.risk = RiskCalculator(risk_config or RiskConfig(
            initial_balance=float(config.initial_balance),
            max_drawdown=config.max_drawdown_pct,
            max_daily_risk=config.daily_loss_limit_pct,
            max_concurrent_positions=config.max_open_positions,
        ))

        self.equity = EquityTracker(initial_balance=config.initial_balance)

        self.barrier = TripleBarrier(
            sl_pct=config.sl_pct,
            tp_pct=config.tp_pct,
            max_bars=config.max_hold_bars,
            trailing=config.trailing,
            trailing_activation=config.trailing_activation,
            trailing_delta=config.trailing_delta,
        )

        self.position: Optional[LivePosition] = None
        self.trade_journal: List[Trade] = []
        self._running = False
        self._halted = False
        self._halt_reason = ""
        self._consecutive_errors = 0
        self._trade_counter = 0
        self._bar_counter = 0
        self._last_report_time = datetime.now(timezone.utc)
        self._last_prices: List[float] = []

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main paper trading loop. Runs until halted or cancelled."""
        self._running = True
        logger.info(f"Paper trading started: {self.cfg.symbol} / {self.cfg.timeframe}")
        self.notifier.alert(f"Paper trading STARTED: {self.cfg.symbol}")

        try:
            while self._running and not self._halted:
                try:
                    await self._tick()
                    self._consecutive_errors = 0
                    await asyncio.sleep(self.cfg.poll_interval_seconds)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._consecutive_errors += 1
                    logger.error(f"Tick error ({self._consecutive_errors}): {e}")
                    self.notifier.error(f"Tick error: {e}")
                    if self._consecutive_errors >= self.cfg.max_consecutive_errors:
                        await self._failsafe_halt(f"Too many consecutive errors: {e}")
                    else:
                        await asyncio.sleep(self.cfg.poll_interval_seconds)
        finally:
            await self._shutdown()

    async def _tick(self) -> None:
        """Single iteration of the trading loop."""
        now = datetime.now(timezone.utc)

        # Daily reset check
        if self.equity.last_daily_reset and \
           (now - self.equity.last_daily_reset) > timedelta(hours=24):
            self._daily_report()
            self.equity.reset_daily()
            self.risk.daily_pnl = 0.0

        # 1. Fetch fresh OHLCV data
        ohlcv_df = await self._fetch_ohlcv()
        if ohlcv_df is None or len(ohlcv_df) < 30:
            return

        current_price = float(ohlcv_df["close"].iloc[-1])
        self._bar_counter += 1

        # 2. Circuit breaker check
        self._last_prices.append(current_price)
        if len(self._last_prices) > self.cfg.circuit_breaker_window:
            self._last_prices = self._last_prices[-self.cfg.circuit_breaker_window:]
        if self._check_circuit_breaker():
            await self._failsafe_halt("Circuit breaker: abnormal price movement")
            return

        # 3. Drawdown / daily loss check
        if self.equity.should_halt_drawdown(self.cfg.max_drawdown_pct):
            await self._failsafe_halt(
                f"Max drawdown {self.cfg.max_drawdown_pct:.0%} breached"
            )
            return
        daily_halted = self.equity.should_halt_daily(self.cfg.daily_loss_limit_pct)

        # 4. If position open: check exit
        if self.position is not None:
            self.position.update_price(Decimal(str(current_price)))
            self.position.bars_since_entry += 1
            exit_triggered = await self._check_position_exit(ohlcv_df)
            if exit_triggered:
                return

        # 5. If no position and not daily-halted: analyze and potentially enter
        if self.position is None and not daily_halted:
            can_trade, reason = self.risk.can_open_trade()
            if not can_trade:
                return

            decision = self.orchestrator.analyze(
                self.cfg.symbol, self.cfg.goliath_timeframe, ohlcv_df
            )

            if decision.action in ("LONG", "SHORT") and \
               decision.confidence >= self.cfg.min_confidence:
                await self._open_position(decision, current_price)

        # 6. Periodic report
        if (now - self._last_report_time) > timedelta(
            hours=self.cfg.report_interval_hours
        ):
            self._daily_report()
            self._last_report_time = now

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _fetch_ohlcv(self) -> Optional[pd.DataFrame]:
        """Fetch OHLCV from exchange and convert to orchestrator format."""
        raw = await self.exchange.fetch_ohlcv(
            self.cfg.symbol, self.cfg.timeframe, limit=500
        )
        if raw is None or len(raw) == 0:
            return None

        df = raw.copy()
        # Orchestrator expects float columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    async def _open_position(self, decision: FallbackDecision,
                              current_price: float) -> None:
        """Place an order and create a LivePosition."""
        self._trade_counter += 1
        trade_id = f"PT-{self._trade_counter:06d}"
        side = "buy" if decision.action == "LONG" else "sell"
        price_dec = Decimal(str(current_price))

        # Calculate size from position_size_pct
        risk_pct = Decimal(str(max(decision.position_size_pct, 0.01)))
        size = (risk_pct * self.equity.current_balance) / price_dec

        try:
            result = await self.exchange.create_order(
                symbol=self.cfg.symbol,
                order_type="market",
                side=side,
                amount=size,
                price=price_dec,
            )
        except Exception as e:
            logger.error(f"Order failed: {e}")
            self.notifier.error(f"Order failed for {trade_id}: {e}")
            return

        fill_price = result.price if result.price > 0 else price_dec
        fill_size = result.filled if result.filled > 0 else size
        direction_int = 1 if decision.action == "LONG" else -1

        barrier_state = self.barrier.open_position(
            fill_price, direction_int, self._bar_counter
        )

        self.position = LivePosition(
            trade_id=trade_id,
            symbol=self.cfg.symbol,
            direction=decision.action,
            entry_price=fill_price,
            entry_time=datetime.now(timezone.utc),
            size=fill_size,
            order_id=result.order_id,
            barrier_state=barrier_state,
        )

        sl = decision.stop_loss if decision.stop_loss else None
        tp = decision.take_profit if decision.take_profit else None
        self.notifier.trade_opened(
            direction=decision.action,
            symbol=self.cfg.symbol,
            price=float(fill_price),
            sl=sl, tp=tp,
        )
        logger.info(
            f"Position opened: {trade_id} {decision.action} {self.cfg.symbol} "
            f"@ {fill_price} size={fill_size}"
        )

    async def _check_position_exit(self, ohlcv_df: pd.DataFrame) -> bool:
        """Check if the open position should exit. Returns True if closed."""
        pos = self.position
        if pos is None:
            return False

        last_row = ohlcv_df.iloc[-1]
        bar_o = Decimal(str(last_row["open"]))
        bar_h = Decimal(str(last_row["high"]))
        bar_l = Decimal(str(last_row["low"]))
        bar_c = Decimal(str(last_row["close"]))

        exit_sig = self.barrier.check_exit(
            pos.barrier_state, bar_o, bar_h, bar_l, bar_c, self._bar_counter
        )

        if exit_sig is not None:
            await self._close_position(exit_sig.exit_price, exit_sig.reason.value)
            return True
        return False

    async def _close_position(self, exit_price: Decimal,
                               exit_reason: str) -> None:
        """Close the current position."""
        pos = self.position
        if pos is None:
            return

        close_side = "sell" if pos.direction == "LONG" else "buy"
        try:
            await self.exchange.create_order(
                symbol=self.cfg.symbol,
                order_type="market",
                side=close_side,
                amount=pos.size,
                price=exit_price,
            )
        except Exception as e:
            logger.error(f"Close order failed: {e}")
            self.notifier.error(f"Close order failed: {e}")

        now = datetime.now(timezone.utc)
        trade = pos.to_trade(exit_price, now, exit_reason)
        self.trade_journal.append(trade)

        self.equity.record_trade(trade.pnl)
        self.risk.update_balance(float(trade.pnl))

        self.orchestrator.record_trade_outcome(
            pos.trade_id, float(trade.pnl), float(trade.pnl) > 0
        )

        self.notifier.trade_closed(
            direction=pos.direction,
            symbol=self.cfg.symbol,
            price=float(exit_price),
            pnl=float(trade.pnl),
        )
        logger.info(
            f"Position closed: {pos.trade_id} | reason={exit_reason} | "
            f"PnL={trade.pnl} ({trade.pnl_pct:.2%}) | "
            f"Equity={self.equity.current_balance}"
        )
        self.position = None

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------

    def _check_circuit_breaker(self) -> bool:
        """Check if price moved more than threshold in window."""
        if len(self._last_prices) < 2:
            return False
        oldest = self._last_prices[0]
        newest = self._last_prices[-1]
        if oldest == 0:
            return False
        change_pct = abs(newest - oldest) / oldest
        return change_pct >= self.cfg.circuit_breaker_pct

    async def _failsafe_halt(self, reason: str) -> None:
        """Emergency halt: close all positions, notify, stop."""
        logger.critical(f"FAILSAFE HALT: {reason}")
        self._halted = True
        self._halt_reason = reason
        self.notifier.alert(f"FAILSAFE HALT: {reason}")

        if self.position is not None:
            try:
                ticker = await self.exchange.fetch_ticker(self.cfg.symbol)
                exit_price = ticker.last if hasattr(ticker, 'last') else self.position.current_price
                await self._close_position(exit_price, "FAILSAFE")
            except Exception as e:
                logger.error(f"Failsafe close failed: {e}")
                self.notifier.error(f"Failsafe close FAILED: {e}")

    async def _shutdown(self) -> None:
        """Graceful shutdown: close positions, final report."""
        if self.position is not None:
            try:
                ticker = await self.exchange.fetch_ticker(self.cfg.symbol)
                exit_price = ticker.last if hasattr(ticker, 'last') else self.position.current_price
                await self._close_position(exit_price, "SHUTDOWN")
            except Exception:
                pass
        self._daily_report()
        logger.info("Paper trading harness shut down")

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _daily_report(self) -> None:
        """Send a daily summary notification."""
        n_trades = len(self.trade_journal)
        if n_trades == 0:
            self.notifier.daily_report(pnl=0.0, win_rate=0.0, n_trades=0)
            return
        wins = sum(1 for t in self.trade_journal if float(t.pnl) > 0)
        win_rate = wins / n_trades
        total_pnl = float(sum(t.pnl for t in self.trade_journal))
        self.notifier.daily_report(pnl=total_pnl, win_rate=win_rate, n_trades=n_trades)

    def get_journal(self) -> List[Trade]:
        """Return the trade journal for analysis."""
        return list(self.trade_journal)

    def get_equity_snapshots(self) -> List[tuple]:
        """Return equity curve snapshots for plotting."""
        return list(self.equity.equity_snapshots)

    def stop(self) -> None:
        """Signal the loop to stop gracefully."""
        self._running = False
