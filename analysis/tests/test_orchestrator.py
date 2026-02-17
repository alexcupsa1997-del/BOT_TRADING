"""Tests for the TradingOrchestrator end-to-end pipeline."""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator import TradingOrchestrator, OrchestratorConfig
from src.ml.decision.fallback import FallbackDecision, FallbackTier
from src.quant.feature_registry import FeatureRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    FeatureRegistry.reset_instance()
    yield
    FeatureRegistry.reset_instance()


@pytest.fixture
def orchestrator():
    """Orchestrator without the neural brain (signal-only mode)."""
    cfg = OrchestratorConfig(enable_brain=False)
    return TradingOrchestrator(cfg)


@pytest.fixture
def ohlcv_200():
    """Synthetic 200-row OHLCV DataFrame."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    close = 1800.0 + np.cumsum(np.random.randn(n) * 2.0)
    high = close + np.abs(np.random.randn(n) * 1.5)
    low = close - np.abs(np.random.randn(n) * 1.5)
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.lognormal(mean=10, sigma=0.5, size=n)
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=dates)


class TestAnalyze:
    def test_returns_fallback_decision(self, orchestrator, ohlcv_200):
        result = orchestrator.analyze("XAUUSD", "H1", ohlcv_200)
        assert isinstance(result, FallbackDecision)

    def test_source_tier_is_labeled(self, orchestrator, ohlcv_200):
        result = orchestrator.analyze("XAUUSD", "H1", ohlcv_200)
        assert result.source_tier in list(FallbackTier)

    def test_position_size_non_negative(self, orchestrator, ohlcv_200):
        result = orchestrator.analyze("XAUUSD", "H1", ohlcv_200)
        assert result.position_size_pct >= 0

    def test_action_is_valid(self, orchestrator, ohlcv_200):
        result = orchestrator.analyze("XAUUSD", "H1", ohlcv_200)
        assert result.action in ("LONG", "SHORT", "HOLD")


class TestShortData:
    def test_does_not_crash_on_short_data(self, orchestrator):
        np.random.seed(42)
        short_df = pd.DataFrame({
            "open": [1800.0] * 10,
            "high": [1801.0] * 10,
            "low": [1799.0] * 10,
            "close": [1800.0] * 10,
            "volume": [1000.0] * 10,
        }, index=pd.date_range("2024-01-01", periods=10, freq="h"))
        result = orchestrator.analyze("XAUUSD", "H1", short_df)
        assert result.action == "HOLD"
        assert result.source_tier == FallbackTier.CONSERVATIVE
