"""
Tests for Paper Trading Harness — Execution Layer

Ref: FUSION_PLAN Fase 6
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.execution.paper_trader import (
    PaperTradingConfig,
    LivePosition,
    EquityTracker,
    PaperTradingHarness,
)
from src.quant.triple_barrier import BarrierState, ExitSignal, ExitReason
from src.quant.risk_manager import RiskConfig
from src.integration.notifier import Notifier, NotifierConfig


# =============================================================================
# HELPERS — Mock exchange, minimal objects
# =============================================================================

@dataclass
class MockOrderResult:
    order_id: str = "ORD-001"
    symbol: str = "BTC/USDT"
    side: str = "buy"
    order_type: str = "market"
    price: Decimal = Decimal("50000")
    amount: Decimal = Decimal("0.01")
    filled: Decimal = Decimal("0.01")
    remaining: Decimal = Decimal("0")
    cost: Decimal = Decimal("500")
    fee: Decimal = Decimal("0.5")
    status: str = "closed"
    timestamp: int = 0


@dataclass
class MockTicker:
    symbol: str = "BTC/USDT"
    bid: Decimal = Decimal("49990")
    ask: Decimal = Decimal("50010")
    last: Decimal = Decimal("50000")
    volume: Decimal = Decimal("1000")
    timestamp: int = 0


def make_ohlcv_df(n: int = 100, start_price: float = 50000.0,
                  trend: float = 0.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = start_price + np.cumsum(np.random.normal(trend, 20, n))
    high = close + np.abs(np.random.normal(10, 5, n))
    low = close - np.abs(np.random.normal(10, 5, n))
    open_ = close + np.random.normal(0, 5, n)
    volume = np.random.uniform(100, 1000, n)
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=dates)


def make_barrier_state(entry_price: Decimal = Decimal("50000"),
                       direction: int = 1) -> BarrierState:
    """Create a minimal BarrierState."""
    sl_pct = Decimal("0.02")
    tp_pct = Decimal("0.03")
    if direction == 1:
        sl = entry_price * (1 - sl_pct)
        tp = entry_price * (1 + tp_pct)
    else:
        sl = entry_price * (1 + sl_pct)
        tp = entry_price * (1 - tp_pct)
    return BarrierState(
        entry_price=entry_price,
        direction=direction,
        sl_level=sl,
        tp_level=tp,
        entry_bar=0,
        max_bars=48,
        trailing=False,
        trailing_activation=Decimal("0"),
        trailing_delta=0.01,
        peak_price=entry_price,
    )


def make_mock_exchange(ohlcv_df: Optional[pd.DataFrame] = None):
    """Create a mock exchange with async methods."""
    exchange = AsyncMock()
    exchange.fetch_ohlcv = AsyncMock(return_value=ohlcv_df or make_ohlcv_df())
    exchange.create_order = AsyncMock(return_value=MockOrderResult())
    exchange.fetch_ticker = AsyncMock(return_value=MockTicker())
    return exchange


def make_mock_orchestrator(action: str = "LONG", confidence: float = 0.85):
    """Create a mock orchestrator returning a fixed decision."""
    from src.ml.decision.fallback import FallbackDecision, FallbackTier
    decision = FallbackDecision(
        action=action,
        confidence=confidence,
        source_tier=FallbackTier.ML_MODEL,
        reasoning="Test signal",
        stop_loss=49000.0,
        take_profit=52000.0,
        position_size_pct=0.05,
    )
    orch = MagicMock()
    orch.analyze = MagicMock(return_value=decision)
    orch.record_trade_outcome = MagicMock()
    return orch


def make_notifier():
    """Create a dry-run notifier."""
    return Notifier(NotifierConfig(enable_console=False, dry_run=True))


# =============================================================================
# TEST LIVE POSITION
# =============================================================================

class TestLivePosition:
    """Tests for LivePosition tracking."""

    def test_update_price_long_profit(self):
        pos = LivePosition(
            trade_id="PT-1", symbol="BTC/USDT", direction="LONG",
            entry_price=Decimal("50000"), entry_time=datetime.now(timezone.utc),
            size=Decimal("0.01"), order_id="ORD-1",
            barrier_state=make_barrier_state(),
        )
        pos.update_price(Decimal("51000"))
        assert pos.unrealized_pnl == Decimal("10.00")  # (51000-50000)*0.01
        assert pos.mfe == Decimal("1000")               # excursion = 1000
        assert pos.mae == Decimal("0")

    def test_update_price_long_loss(self):
        pos = LivePosition(
            trade_id="PT-1", symbol="BTC/USDT", direction="LONG",
            entry_price=Decimal("50000"), entry_time=datetime.now(timezone.utc),
            size=Decimal("0.01"), order_id="ORD-1",
            barrier_state=make_barrier_state(),
        )
        pos.update_price(Decimal("49000"))
        assert pos.unrealized_pnl == Decimal("-10.00")
        assert pos.mae == Decimal("1000")
        assert pos.mfe == Decimal("0")

    def test_update_price_short_profit(self):
        pos = LivePosition(
            trade_id="PT-1", symbol="BTC/USDT", direction="SHORT",
            entry_price=Decimal("50000"), entry_time=datetime.now(timezone.utc),
            size=Decimal("0.01"), order_id="ORD-1",
            barrier_state=make_barrier_state(direction=-1),
        )
        pos.update_price(Decimal("49000"))
        assert pos.unrealized_pnl == Decimal("10.00")
        assert pos.mfe == Decimal("1000")

    def test_update_price_short_loss(self):
        pos = LivePosition(
            trade_id="PT-1", symbol="BTC/USDT", direction="SHORT",
            entry_price=Decimal("50000"), entry_time=datetime.now(timezone.utc),
            size=Decimal("0.01"), order_id="ORD-1",
            barrier_state=make_barrier_state(direction=-1),
        )
        pos.update_price(Decimal("51000"))
        assert pos.unrealized_pnl == Decimal("-10.00")
        assert pos.mae == Decimal("1000")

    def test_mae_mfe_tracking(self):
        """MAE/MFE should track worst and best excursions."""
        pos = LivePosition(
            trade_id="PT-1", symbol="BTC/USDT", direction="LONG",
            entry_price=Decimal("50000"), entry_time=datetime.now(timezone.utc),
            size=Decimal("0.01"), order_id="ORD-1",
            barrier_state=make_barrier_state(),
        )
        # Price goes up, then down, then up more
        pos.update_price(Decimal("51000"))   # +1000 MFE
        pos.update_price(Decimal("49500"))   # -500 MAE
        pos.update_price(Decimal("52000"))   # +2000 new MFE
        pos.update_price(Decimal("49000"))   # -1000 new MAE

        assert pos.mfe == Decimal("2000")
        assert pos.mae == Decimal("1000")

    def test_to_trade_conversion(self):
        """LivePosition should convert to a Trade record correctly."""
        entry_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        exit_time = datetime(2025, 1, 2, tzinfo=timezone.utc)
        pos = LivePosition(
            trade_id="PT-1", symbol="BTC/USDT", direction="LONG",
            entry_price=Decimal("50000"), entry_time=entry_time,
            size=Decimal("0.1"), order_id="ORD-1",
            barrier_state=make_barrier_state(),
        )
        pos.update_price(Decimal("51500"))  # update MFE
        trade = pos.to_trade(Decimal("51000"), exit_time, "TAKE_PROFIT")

        assert trade.direction == "LONG"
        assert trade.entry_price == Decimal("50000")
        assert trade.exit_price == Decimal("51000")
        assert trade.pnl == Decimal("100.0")       # (51000-50000)*0.1
        assert trade.exit_reason == "TAKE_PROFIT"
        assert trade.entry_tag == "paper_live"
        assert trade.duration_hours == 24.0

    def test_to_trade_short(self):
        """Verify short P&L is computed correctly."""
        entry_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        exit_time = datetime(2025, 1, 1, 12, tzinfo=timezone.utc)
        pos = LivePosition(
            trade_id="PT-2", symbol="BTC/USDT", direction="SHORT",
            entry_price=Decimal("50000"), entry_time=entry_time,
            size=Decimal("0.1"), order_id="ORD-2",
            barrier_state=make_barrier_state(direction=-1),
        )
        trade = pos.to_trade(Decimal("49000"), exit_time, "STOP_LOSS")
        assert trade.pnl == Decimal("100.0")  # Short profit: (50000-49000)*0.1
        assert trade.pnl_pct == pytest.approx(0.02, abs=1e-6)


# =============================================================================
# TEST EQUITY TRACKER
# =============================================================================

class TestEquityTracker:
    """Tests for EquityTracker."""

    def test_initial_state(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        assert eq.current_balance == Decimal("10000")
        assert eq.peak_balance == Decimal("10000")
        assert eq.drawdown_pct == 0.0

    def test_record_trade_profit(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("500"))
        assert eq.current_balance == Decimal("10500")
        assert eq.peak_balance == Decimal("10500")
        assert eq.drawdown_pct == 0.0

    def test_record_trade_loss(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("-200"))
        assert eq.current_balance == Decimal("9800")
        assert eq.peak_balance == Decimal("10000")
        assert eq.drawdown_pct == pytest.approx(0.02)

    def test_drawdown_after_peak(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("1000"))   # Peak = 11000
        eq.record_trade(Decimal("-500"))   # Current = 10500
        assert eq.peak_balance == Decimal("11000")
        assert eq.drawdown_pct == pytest.approx(500 / 11000, abs=1e-6)

    def test_should_halt_drawdown(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("-1500"))  # 15% drawdown
        assert eq.should_halt_drawdown(0.15) is True
        assert eq.should_halt_drawdown(0.20) is False

    def test_should_halt_daily(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("-500"))  # 5% daily loss
        assert eq.should_halt_daily(0.05) is True
        assert eq.should_halt_daily(0.10) is False

    def test_daily_reset(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("-300"))
        eq.reset_daily()
        assert eq.daily_start_balance == Decimal("9700")
        assert eq.daily_pnl_pct == 0.0

    def test_equity_snapshots(self):
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("100"))
        eq.record_trade(Decimal("-50"))
        assert len(eq.equity_snapshots) == 2
        assert eq.equity_snapshots[-1][1] == 10050.0


# =============================================================================
# TEST PAPER TRADING HARNESS (async, mocked exchange)
# =============================================================================

class TestPaperTradingHarness:
    """Async tests for PaperTradingHarness."""

    def _make_harness(self, action="LONG", confidence=0.85, ohlcv=None):
        """Build a harness with mocked dependencies."""
        config = PaperTradingConfig(
            symbol="BTC/USDT",
            timeframe="1h",
            poll_interval_seconds=0.01,  # Fast for tests
            min_confidence=0.65,
            initial_balance=Decimal("10000"),
            max_drawdown_pct=0.15,
            daily_loss_limit_pct=0.05,
        )
        exchange = make_mock_exchange(ohlcv)
        orch = make_mock_orchestrator(action, confidence)
        notifier = make_notifier()

        harness = PaperTradingHarness(
            config=config,
            exchange=exchange,
            orchestrator=orch,
            notifier=notifier,
        )
        return harness

    @pytest.mark.asyncio
    async def test_tick_opens_position(self):
        """A LONG signal with high confidence should open a position."""
        harness = self._make_harness(action="LONG", confidence=0.85)

        await harness._tick()

        assert harness.position is not None
        assert harness.position.direction == "LONG"
        assert harness.position.trade_id == "PT-000001"
        harness.exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_hold_no_position(self):
        """A HOLD signal should not open a position."""
        harness = self._make_harness(action="HOLD", confidence=0.50)

        await harness._tick()

        assert harness.position is None
        harness.exchange.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_tick_low_confidence_no_position(self):
        """Below min_confidence, no position should open."""
        harness = self._make_harness(action="LONG", confidence=0.30)

        await harness._tick()

        assert harness.position is None

    @pytest.mark.asyncio
    async def test_close_position_records_trade(self):
        """Closing a position should add to journal and update equity."""
        harness = self._make_harness()
        await harness._tick()  # Opens position
        assert harness.position is not None

        # Manually close
        await harness._close_position(Decimal("51000"), "TAKE_PROFIT")

        assert harness.position is None
        assert len(harness.trade_journal) == 1
        trade = harness.trade_journal[0]
        assert trade.exit_reason == "TAKE_PROFIT"
        assert float(trade.pnl) > 0
        harness.orchestrator.record_trade_outcome.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers(self):
        """Price spike > threshold should trigger failsafe halt."""
        harness = self._make_harness()
        # Simulate prices with large spike
        harness._last_prices = [50000, 50100, 50200, 56000]  # >10% spike
        harness.cfg.circuit_breaker_window = 5

        assert harness._check_circuit_breaker() is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_normal(self):
        """Normal price movement should not trigger circuit breaker."""
        harness = self._make_harness()
        harness._last_prices = [50000, 50100, 50050, 50200]

        assert harness._check_circuit_breaker() is False

    @pytest.mark.asyncio
    async def test_failsafe_closes_position(self):
        """Failsafe halt should close open position and set halted flag."""
        harness = self._make_harness()
        await harness._tick()  # Open position
        assert harness.position is not None

        await harness._failsafe_halt("Test halt")

        assert harness._halted is True
        assert harness.position is None
        assert len(harness.trade_journal) == 1
        assert harness.trade_journal[0].exit_reason == "FAILSAFE"

    @pytest.mark.asyncio
    async def test_failsafe_no_position(self):
        """Failsafe without a position should just halt."""
        harness = self._make_harness(action="HOLD")
        await harness._failsafe_halt("No position halt")

        assert harness._halted is True
        assert harness.position is None
        assert len(harness.trade_journal) == 0

    @pytest.mark.asyncio
    async def test_journal_collects_trades(self):
        """Trade journal should accumulate over multiple open/close cycles."""
        harness = self._make_harness()

        # First trade
        await harness._tick()
        await harness._close_position(Decimal("51000"), "TAKE_PROFIT")

        # Second trade
        await harness._tick()
        await harness._close_position(Decimal("49500"), "STOP_LOSS")

        journal = harness.get_journal()
        assert len(journal) == 2
        assert journal[0].exit_reason == "TAKE_PROFIT"
        assert journal[1].exit_reason == "STOP_LOSS"

    @pytest.mark.asyncio
    async def test_daily_report(self):
        """Daily report should not raise even with no trades."""
        harness = self._make_harness()
        harness._daily_report()  # Should not raise

    @pytest.mark.asyncio
    async def test_daily_report_with_trades(self):
        """Daily report with trades should compute win rate."""
        harness = self._make_harness()
        await harness._tick()
        await harness._close_position(Decimal("51000"), "TAKE_PROFIT")
        harness._daily_report()  # Should not raise

    @pytest.mark.asyncio
    async def test_equity_snapshots(self):
        """Equity snapshots should grow with trades."""
        harness = self._make_harness()
        await harness._tick()
        await harness._close_position(Decimal("51000"), "TP")

        snaps = harness.get_equity_snapshots()
        assert len(snaps) >= 1

    @pytest.mark.asyncio
    async def test_stop_method(self):
        """stop() should set _running to False."""
        harness = self._make_harness()
        harness.stop()
        assert harness._running is False

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_none(self):
        """If exchange returns None, tick should skip gracefully."""
        harness = self._make_harness()
        harness.exchange.fetch_ohlcv = AsyncMock(return_value=None)

        await harness._tick()  # Should not raise
        assert harness.position is None

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_small(self):
        """If exchange returns < 30 bars, tick should skip."""
        harness = self._make_harness()
        harness.exchange.fetch_ohlcv = AsyncMock(
            return_value=make_ohlcv_df(n=10)
        )

        await harness._tick()
        assert harness.position is None

    @pytest.mark.asyncio
    async def test_max_consecutive_errors_triggers_halt(self):
        """Exceeding max_consecutive_errors should halt."""
        harness = self._make_harness()
        harness.cfg.max_consecutive_errors = 3
        harness._consecutive_errors = 2

        # Make tick raise an error
        harness.exchange.fetch_ohlcv = AsyncMock(
            side_effect=RuntimeError("Network down")
        )

        # The run() loop catches the error and increments counter
        # Simulate what run() does:
        try:
            await harness._tick()
        except RuntimeError:
            harness._consecutive_errors += 1
            if harness._consecutive_errors >= harness.cfg.max_consecutive_errors:
                await harness._failsafe_halt("Too many errors")

        assert harness._halted is True

    @pytest.mark.asyncio
    async def test_order_failure_skips_position(self):
        """If create_order raises, no position should be opened."""
        harness = self._make_harness()
        harness.exchange.create_order = AsyncMock(
            side_effect=RuntimeError("Exchange error")
        )

        await harness._tick()  # Should not raise
        assert harness.position is None

    @pytest.mark.asyncio
    async def test_drawdown_halt(self):
        """Drawdown beyond limit should prevent new positions."""
        harness = self._make_harness()
        # Simulate heavy losses
        harness.equity.record_trade(Decimal("-2000"))  # 20% loss on 10k

        await harness._tick()

        # Should have triggered failsafe halt
        assert harness._halted is True

    @pytest.mark.asyncio
    async def test_short_position_opens(self):
        """A SHORT signal should open a short position."""
        harness = self._make_harness(action="SHORT", confidence=0.90)

        await harness._tick()

        assert harness.position is not None
        assert harness.position.direction == "SHORT"
