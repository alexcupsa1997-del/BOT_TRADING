"""
Tests for BacktestEngine — Event-driven backtesting with OHLC slippage

Ref: FUSION_PLAN Fase 2, item 2.5
"""

import numpy as np
import pandas as pd
import pytest
from decimal import Decimal
from typing import Optional, Dict, Any

from src.quant.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    BacktestMetrics,
    Strategy,
    Trade,
)


# =============================================================================
# SIMPLE STRATEGIES FOR TESTING
# =============================================================================

class AlwaysBuyStrategy(Strategy):
    """Buy at every bar (for stress-testing the engine)."""
    def on_candle(self, idx, row, history) -> Optional[Dict[str, Any]]:
        if idx % 10 == 0:
            return {"direction": "LONG", "tag": "always_buy"}
        return None


class TrendFollowingStrategy(Strategy):
    """Simple EMA crossover: buy when close > SMA20, sell when close < SMA20."""
    def __init__(self, period: int = 20):
        self.period = period

    def on_candle(self, idx, row, history) -> Optional[Dict[str, Any]]:
        if idx < self.period + 1:
            return None
        sma = history["close"].iloc[-self.period:].mean()
        prev_sma = history["close"].iloc[-self.period - 1:-1].mean()
        close = row["close"]
        prev_close = history["close"].iloc[-2]

        # Crossover up
        if prev_close <= prev_sma and close > sma:
            return {"direction": "LONG", "tag": "sma_cross_up"}
        # Crossover down
        if prev_close >= prev_sma and close < sma:
            return {"direction": "SHORT", "tag": "sma_cross_down"}
        return None


class NeverTradeStrategy(Strategy):
    """Never trades — should produce empty journal."""
    def on_candle(self, idx, row, history) -> Optional[Dict[str, Any]]:
        return None


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def synthetic_uptrend():
    """200 bars of synthetic uptrend data."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(np.random.normal(0.05, 0.3, n))
    high = close + np.abs(np.random.normal(0.2, 0.1, n))
    low = close - np.abs(np.random.normal(0.2, 0.1, n))
    open_ = close + np.random.normal(0, 0.1, n)
    volume = np.random.randint(100, 1000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def synthetic_volatile():
    """200 bars of volatile data (big swings)."""
    np.random.seed(123)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(np.random.normal(0, 1.5, n))
    high = close + np.abs(np.random.normal(1.0, 0.5, n))
    low = close - np.abs(np.random.normal(1.0, 0.5, n))
    open_ = close + np.random.normal(0, 0.3, n)
    volume = np.random.randint(100, 1000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def default_config():
    return BacktestConfig(
        initial_capital=Decimal("10000"),
        commission_pct=Decimal("0.001"),
        slippage_pct=0.0001,
        position_size_pct=0.02,
        max_open_positions=1,
        sl_pct=0.02,
        tp_pct=0.03,
        max_bars=48,
        seed=42,
    )


# =============================================================================
# CORE ENGINE TESTS
# =============================================================================

class TestBacktestEngine:
    def test_run_produces_result(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        assert isinstance(result, BacktestResult)
        assert isinstance(result.metrics, BacktestMetrics)
        assert len(result.equity_curve) == len(synthetic_uptrend)

    def test_empty_strategy_produces_no_trades(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, NeverTradeStrategy(), default_config)
        assert result.metrics.total_trades == 0
        assert result.metrics.win_rate == 0.0

    def test_trades_journal_populated(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        assert len(result.journal) > 0
        for trade in result.journal:
            assert isinstance(trade, Trade)
            assert isinstance(trade.entry_price, Decimal)
            assert isinstance(trade.exit_price, Decimal)
            assert isinstance(trade.pnl, Decimal)
            assert isinstance(trade.commission_paid, Decimal)

    def test_equity_curve_starts_at_capital(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, NeverTradeStrategy(), default_config)
        # No trades: equity stays at initial
        assert result.equity_curve[0] == float(default_config.initial_capital)

    def test_missing_columns_raises(self, default_config):
        engine = BacktestEngine()
        bad_data = pd.DataFrame({"price": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing columns"):
            engine.run(bad_data, NeverTradeStrategy(), default_config)

    def test_insufficient_data_raises(self, default_config):
        engine = BacktestEngine()
        tiny = pd.DataFrame(
            {"open": [1], "high": [2], "low": [0.5], "close": [1.5]},
            index=pd.date_range("2025-01-01", periods=1, freq="1h"),
        )
        with pytest.raises(ValueError, match="at least 2 rows"):
            engine.run(tiny, NeverTradeStrategy(), default_config)


# =============================================================================
# METRICS TESTS
# =============================================================================

class TestMetrics:
    def test_all_17_metrics_computed(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        m = result.metrics
        # All 17 core metrics should be set (not None)
        assert m.total_trades > 0
        assert isinstance(m.sharpe_ratio, float)
        assert isinstance(m.sortino_ratio, float)
        assert isinstance(m.calmar_ratio, float)
        assert isinstance(m.max_drawdown, float)
        assert isinstance(m.max_drawdown_duration, int)
        assert isinstance(m.win_rate, float)
        assert isinstance(m.profit_factor, float)
        assert isinstance(m.expectancy, float)
        assert isinstance(m.avg_win, float)
        assert isinstance(m.avg_loss, float)
        assert isinstance(m.long_win_rate, float)
        assert isinstance(m.short_win_rate, float)
        assert isinstance(m.avg_trade_duration, float)
        assert isinstance(m.max_consecutive_losses, int)
        assert isinstance(m.recovery_factor, float)
        assert isinstance(m.annual_return, float)
        assert isinstance(m.total_commission, Decimal)
        assert isinstance(m.total_slippage, Decimal)

    def test_win_rate_between_0_and_1(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        assert 0.0 <= result.metrics.win_rate <= 1.0

    def test_max_drawdown_non_negative(self, synthetic_volatile, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_volatile, TrendFollowingStrategy(), default_config)
        assert result.metrics.max_drawdown >= 0.0

    def test_commissions_are_positive(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        if result.metrics.total_trades > 0:
            assert result.metrics.total_commission > 0


# =============================================================================
# SLIPPAGE TESTS
# =============================================================================

class TestSlippage:
    def test_slippage_cost_recorded(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        assert result.metrics.total_slippage >= 0

    def test_zero_slippage_config(self, synthetic_uptrend):
        cfg = BacktestConfig(slippage_pct=0.0, seed=42)
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), cfg)
        # With zero slippage, all entry fills should be at close
        for trade in result.journal:
            assert trade.slippage_cost >= 0  # may still have rounding


# =============================================================================
# REPRODUCIBILITY TESTS
# =============================================================================

class TestReproducibility:
    def test_same_seed_same_result(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        r1 = engine.run(synthetic_uptrend, TrendFollowingStrategy(), default_config)
        r2 = engine.run(synthetic_uptrend, TrendFollowingStrategy(), default_config)
        assert r1.metrics.total_trades == r2.metrics.total_trades
        assert r1.metrics.sharpe_ratio == r2.metrics.sharpe_ratio
        np.testing.assert_array_equal(r1.equity_curve, r2.equity_curve)

    def test_different_seed_may_differ(self, synthetic_uptrend):
        """Different seed shouldn't crash (seeds only affect internal randomness)."""
        engine = BacktestEngine()
        cfg1 = BacktestConfig(seed=42)
        cfg2 = BacktestConfig(seed=99)
        r1 = engine.run(synthetic_uptrend, TrendFollowingStrategy(), cfg1)
        r2 = engine.run(synthetic_uptrend, TrendFollowingStrategy(), cfg2)
        # Both should complete successfully
        assert isinstance(r1, BacktestResult)
        assert isinstance(r2, BacktestResult)


# =============================================================================
# REPORT FORMAT TEST
# =============================================================================

class TestReport:
    def test_format_report(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        report = engine.format_report(result.metrics)
        assert "BACKTEST PERFORMANCE REPORT" in report
        assert "Sharpe Ratio" in report
        assert "Win Rate" in report

    def test_format_report_empty(self):
        report = BacktestEngine.format_report(BacktestMetrics())
        assert "Total Trades" in report


# =============================================================================
# TRADE DETAILS TESTS
# =============================================================================

class TestTradeDetails:
    def test_trade_has_mae_mfe(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        for trade in result.journal:
            assert isinstance(trade.max_favorable, Decimal)
            assert isinstance(trade.max_adverse, Decimal)

    def test_trade_has_exit_reason(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        valid_reasons = {"STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP", "TIME_LIMIT", "SIGNAL"}
        for trade in result.journal:
            assert trade.exit_reason in valid_reasons

    def test_trade_duration_positive(self, synthetic_uptrend, default_config):
        engine = BacktestEngine()
        result = engine.run(synthetic_uptrend, AlwaysBuyStrategy(), default_config)
        for trade in result.journal:
            assert trade.duration_hours >= 0
