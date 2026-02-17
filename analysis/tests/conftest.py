"""Shared test fixtures for the analysis test suite."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv_df():
    """Synthetic OHLCV DataFrame with 200 rows (enough for rolling windows)."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h")

    close = 1800.0 + np.cumsum(np.random.randn(n) * 2.0)
    high = close + np.abs(np.random.randn(n) * 1.5)
    low = close - np.abs(np.random.randn(n) * 1.5)
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.lognormal(mean=10, sigma=0.5, size=n)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)


@pytest.fixture
def price_series(ohlcv_df):
    """Close price series extracted from OHLCV fixture."""
    return ohlcv_df["close"]
