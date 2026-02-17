"""
Integration Tests — Full Pipeline: Orchestrator -> Risk -> Exchange -> Paper

These tests wire real (non-mocked) orchestrator components with a mocked
exchange to verify the end-to-end data flow.

Ref: FUSION_PLAN Fase 6
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from src.orchestrator import TradingOrchestrator, OrchestratorConfig
from src.ml.decision.fallback import FallbackDecision, FallbackTier
from src.quant.feature_registry import FeatureRegistry
from src.quant.risk_manager import RiskCalculator, RiskConfig
from src.execution.paper_trader import (
    PaperTradingConfig,
    PaperTradingHarness,
    EquityTracker,
)
from src.integration.notifier import Notifier, NotifierConfig


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_registry():
    FeatureRegistry.reset_instance()
    yield
    FeatureRegistry.reset_instance()


@dataclass
class MockOrderResult:
    order_id: str = "ORD-INT-001"
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


def make_synthetic_ohlcv(n: int = 200, start: float = 50000.0) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = start + np.cumsum(np.random.normal(0.5, 20, n))
    high = close + np.abs(np.random.normal(10, 5, n))
    low = close - np.abs(np.random.normal(10, 5, n))
    open_ = close + np.random.normal(0, 5, n)
    volume = np.random.lognormal(mean=10, sigma=0.5, size=n)
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=dates)


def make_mock_exchange(ohlcv_df=None):
    exchange = AsyncMock()
    exchange.fetch_ohlcv = AsyncMock(
        return_value=ohlcv_df if ohlcv_df is not None else make_synthetic_ohlcv()
    )
    exchange.create_order = AsyncMock(return_value=MockOrderResult())
    exchange.fetch_ticker = AsyncMock(return_value=MockTicker())
    return exchange


def make_notifier():
    return Notifier(NotifierConfig(enable_console=False, dry_run=True))


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestOrchestratorProducesSignal:
    """Verify the real orchestrator produces actionable output on synthetic data."""

    def test_orchestrator_produces_decision(self):
        """Real orchestrator should return a FallbackDecision."""
        orch = TradingOrchestrator(OrchestratorConfig(enable_brain=False))
        ohlcv = make_synthetic_ohlcv()
        decision = orch.analyze("BTCUSDT", "H1", ohlcv)

        assert isinstance(decision, FallbackDecision)
        assert decision.action in ("LONG", "SHORT", "HOLD")
        assert 0.0 <= decision.confidence <= 1.0

    def test_orchestrator_with_short_data(self):
        """Insufficient data should return HOLD."""
        orch = TradingOrchestrator(OrchestratorConfig(enable_brain=False))
        ohlcv = make_synthetic_ohlcv(n=10)
        decision = orch.analyze("BTCUSDT", "H1", ohlcv)

        assert decision.action == "HOLD"
        assert decision.confidence == 0.0


class TestRiskManagerGates:
    """Verify RiskCalculator correctly gates new trades."""

    def test_can_trade_initially(self):
        risk = RiskCalculator(RiskConfig(initial_balance=10000.0))
        allowed, reason = risk.can_open_trade()
        assert allowed is True

    def test_cannot_trade_after_max_drawdown(self):
        risk = RiskCalculator(RiskConfig(
            initial_balance=10000.0,
            max_drawdown=0.10,
            max_daily_risk=1.0,  # Disable daily limit to isolate drawdown
        ))
        # Simulate 15% loss
        risk.update_balance(-1500.0)
        allowed, reason = risk.can_open_trade()
        assert allowed is False
        assert "drawdown" in reason.lower()


class TestPipelineIntegration:
    """End-to-end: exchange data -> orchestrator -> risk -> order."""

    @pytest.mark.asyncio
    async def test_pipeline_exchange_to_decision_to_order(self):
        """Full pipeline with real orchestrator, mocked exchange."""
        ohlcv = make_synthetic_ohlcv()
        exchange = make_mock_exchange(ohlcv)

        orch = TradingOrchestrator(OrchestratorConfig(enable_brain=False))

        config = PaperTradingConfig(
            symbol="BTC/USDT",
            timeframe="1h",
            min_confidence=0.0,  # Accept any signal for testing
            initial_balance=Decimal("10000"),
        )
        harness = PaperTradingHarness(
            config=config,
            exchange=exchange,
            orchestrator=orch,
            notifier=make_notifier(),
        )

        await harness._tick()

        # Either a position was opened (LONG/SHORT) or not (HOLD)
        decision = orch.analyze("BTC/USDT", "H1", ohlcv)
        if decision.action in ("LONG", "SHORT"):
            # Should have attempted to open
            assert harness.position is not None or exchange.create_order.called
        else:
            # HOLD — no position
            assert harness.position is None

    @pytest.mark.asyncio
    async def test_failsafe_triggers_on_repeated_errors(self):
        """5 consecutive errors should trigger failsafe halt."""
        exchange = make_mock_exchange()
        exchange.fetch_ohlcv = AsyncMock(side_effect=RuntimeError("Connection lost"))

        orch = MagicMock()
        config = PaperTradingConfig(
            symbol="BTC/USDT",
            max_consecutive_errors=3,
            poll_interval_seconds=0.01,
        )
        harness = PaperTradingHarness(
            config=config,
            exchange=exchange,
            orchestrator=orch,
            notifier=make_notifier(),
        )

        # Simulate what run() does — errors accumulate
        for _ in range(3):
            try:
                await harness._tick()
            except RuntimeError:
                harness._consecutive_errors += 1
                if harness._consecutive_errors >= config.max_consecutive_errors:
                    await harness._failsafe_halt("Too many errors")
                    break

        assert harness._halted is True

    @pytest.mark.asyncio
    async def test_journal_feeds_monte_carlo(self):
        """Trade journal from paper trading should feed into Monte Carlo."""
        from src.quant.monte_carlo import MonteCarloSimulator

        ohlcv = make_synthetic_ohlcv()
        exchange = make_mock_exchange(ohlcv)

        orch = TradingOrchestrator(OrchestratorConfig(enable_brain=False))

        config = PaperTradingConfig(
            symbol="BTC/USDT",
            min_confidence=0.0,
            initial_balance=Decimal("10000"),
        )
        harness = PaperTradingHarness(
            config=config,
            exchange=exchange,
            orchestrator=orch,
            notifier=make_notifier(),
        )

        # Open and close a few trades manually
        for i in range(5):
            await harness._tick()
            if harness.position is not None:
                exit_price = Decimal(str(50000 + (i * 100 - 200)))
                await harness._close_position(exit_price, "TEST")

        journal = harness.get_journal()
        if len(journal) >= 2:
            sim = MonteCarloSimulator(journal, n_simulations=100, seed=42)
            result = sim.full_report()
            assert 0.0 <= result.risk_of_ruin <= 1.0
            assert result.n_simulations == 100

    @pytest.mark.asyncio
    async def test_equity_tracker_halts_on_drawdown(self):
        """EquityTracker drawdown halt should prevent new trades."""
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("-2000"))  # 20% drawdown

        assert eq.should_halt_drawdown(0.15) is True
        assert eq.drawdown_pct >= 0.15

    @pytest.mark.asyncio
    async def test_daily_loss_halt(self):
        """Daily loss limit should prevent further trading."""
        eq = EquityTracker(initial_balance=Decimal("10000"))
        eq.record_trade(Decimal("-600"))  # 6% daily loss

        assert eq.should_halt_daily(0.05) is True
        assert eq.daily_pnl_pct <= -0.05
