"""
Tests for the Signal Server — Gateway ↔ Analysis bridge.

Uses FastAPI TestClient (synchronous) via httpx.
"""

import pytest
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd

from src.quant.feature_registry import FeatureRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    FeatureRegistry.reset_instance()
    yield
    FeatureRegistry.reset_instance()


@pytest.fixture
def client():
    """Create a FastAPI TestClient with lifespan context."""
    from src.integration.signal_server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "analysis"


# =============================================================================
# PREDICT ENDPOINT
# =============================================================================

class TestPredict:
    def test_predict_returns_valid_signal(self, client):
        """Predict endpoint should return a valid AI signal."""
        resp = client.get("/predict/XAUUSD?timeframe=H1")
        assert resp.status_code == 200
        data = resp.json()

        assert "direction" in data
        assert data["direction"] in ("LONG", "SHORT", "HOLD")
        assert "confidence" in data
        assert 0.0 <= data["confidence"] <= 1.0
        assert "source_tier" in data
        assert "reasoning" in data

    def test_predict_different_symbols(self, client):
        """Different symbols should all return valid signals."""
        for symbol in ["EURUSD", "BTCUSDT", "XAUUSD"]:
            resp = client.get(f"/predict/{symbol}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["direction"] in ("LONG", "SHORT", "HOLD")

    def test_predict_default_timeframe(self, client):
        """Without timeframe param, should default to H1."""
        resp = client.get("/predict/EURUSD")
        assert resp.status_code == 200

    def test_predict_custom_timeframe(self, client):
        """Custom timeframe should be accepted."""
        resp = client.get("/predict/EURUSD?timeframe=M15")
        assert resp.status_code == 200

    def test_predict_has_levels(self, client):
        """Signal should include stop_loss and take_profit."""
        resp = client.get("/predict/XAUUSD")
        data = resp.json()
        assert "stop_loss" in data
        assert "take_profit" in data
        assert "position_size_pct" in data


# =============================================================================
# SYMBOL NORMALIZATION
# =============================================================================

class TestNormalization:
    def test_normalize_known_symbols(self):
        from src.integration.signal_server import _normalize_symbol
        assert _normalize_symbol("XAUUSD") == "XAU/USD"
        assert _normalize_symbol("EURUSD") == "EUR/USD"
        assert _normalize_symbol("BTCUSDT") == "BTC/USDT"

    def test_normalize_unknown_passthrough(self):
        from src.integration.signal_server import _normalize_symbol
        assert _normalize_symbol("CUSTOM123") == "CUSTOM123"

    def test_timeframe_mapping(self):
        from src.integration.signal_server import _tf_to_ccxt
        assert _tf_to_ccxt("H1") == "1h"
        assert _tf_to_ccxt("M5") == "5m"
        assert _tf_to_ccxt("D1") == "1d"
        assert _tf_to_ccxt("1h") == "1h"  # passthrough


# =============================================================================
# DATA PROVIDER
# =============================================================================

class TestDataProvider:
    def test_synthetic_data_generation(self):
        from src.integration.signal_server import DataProvider
        provider = DataProvider()
        df = provider._generate_synthetic("XAUUSD", n=200)
        assert len(df) == 200
        assert set(df.columns) == {"open", "high", "low", "close", "volume"}

    def test_synthetic_different_symbols(self):
        from src.integration.signal_server import DataProvider
        provider = DataProvider()
        btc = provider._generate_synthetic("BTCUSD", n=100)
        xau = provider._generate_synthetic("XAUUSD", n=100)
        # Different base prices
        assert abs(btc["close"].mean() - xau["close"].mean()) > 1000
