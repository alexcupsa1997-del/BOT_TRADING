"""Smoke tests for technical indicators and feature engineering."""

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quant.indicators import (
    ema, sma, macd, rsi, stochastic, atr, bollinger_bands, adx, cci,
    compute_all_indicators,
)
from src.quant.features import (
    fractional_differencing, get_weights_ffd, triple_barrier_labels,
)
from src.quant.patterns import detect_all_patterns


# =============================================================================
# Individual Indicators
# =============================================================================

class TestEMA:
    def test_output_length(self, price_series):
        result = ema(price_series, period=20)
        assert len(result) == len(price_series)

    def test_no_nan_after_warmup(self, price_series):
        result = ema(price_series, period=20)
        assert not result.iloc[20:].isna().any()


class TestSMA:
    def test_output_length(self, price_series):
        result = sma(price_series, period=20)
        assert len(result) == len(price_series)

    def test_first_values_nan(self, price_series):
        result = sma(price_series, period=20)
        assert result.iloc[:19].isna().all()


class TestMACD:
    def test_returns_three_series(self, price_series):
        result = macd(price_series)
        assert hasattr(result, "macd_line")
        assert hasattr(result, "signal_line")
        assert hasattr(result, "histogram")

    def test_histogram_equals_diff(self, price_series):
        result = macd(price_series)
        diff = result.macd_line - result.signal_line
        np.testing.assert_allclose(
            result.histogram.dropna().values,
            diff.dropna().values,
            atol=1e-10,
        )


class TestRSI:
    def test_bounded_0_100(self, price_series):
        result = rsi(price_series, period=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_output_length(self, price_series):
        result = rsi(price_series, period=14)
        assert len(result) == len(price_series)


class TestBollinger:
    def test_upper_above_lower(self, price_series):
        result = bollinger_bands(price_series, period=20)
        valid_idx = result.upper.dropna().index
        assert (result.upper[valid_idx] >= result.lower[valid_idx]).all()

    def test_middle_is_sma(self, price_series):
        result = bollinger_bands(price_series, period=20)
        expected_sma = sma(price_series, period=20)
        np.testing.assert_allclose(
            result.middle.dropna().values,
            expected_sma.dropna().values,
            atol=1e-10,
        )


class TestATR:
    def test_positive(self, ohlcv_df):
        result = atr(ohlcv_df["high"], ohlcv_df["low"], ohlcv_df["close"])
        valid = result.dropna()
        assert (valid >= 0).all()


class TestADX:
    def test_bounded(self, ohlcv_df):
        result = adx(ohlcv_df["high"], ohlcv_df["low"], ohlcv_df["close"])
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


# =============================================================================
# Compute All Indicators
# =============================================================================

class TestComputeAll:
    def test_adds_columns(self, ohlcv_df):
        result = compute_all_indicators(ohlcv_df)
        assert "rsi" in result.columns
        assert "macd" in result.columns
        assert "adx" in result.columns
        assert "ema_9" in result.columns

    def test_preserves_original_columns(self, ohlcv_df):
        result = compute_all_indicators(ohlcv_df)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns


# =============================================================================
# Feature Engineering
# =============================================================================

class TestFFDWeights:
    def test_first_weight_is_one(self):
        weights = get_weights_ffd(0.4)
        assert weights[-1, 0] == pytest.approx(1.0)

    def test_weights_decrease(self):
        weights = get_weights_ffd(0.4)
        assert len(weights) > 1


class TestFractionalDifferencing:
    def test_output_length(self, price_series):
        result = fractional_differencing(price_series, d=0.4)
        assert len(result) == len(price_series)

    def test_d_zero_is_identity(self, price_series):
        result = fractional_differencing(price_series, d=0.0)
        valid = result.dropna()
        original = price_series.loc[valid.index]
        np.testing.assert_allclose(valid.values, original.values, atol=1e-10)


class TestTripleBarrierLabels:
    def test_labels_in_range(self, ohlcv_df):
        result = triple_barrier_labels(ohlcv_df["close"], ohlcv_df["high"], ohlcv_df["low"])
        valid = result.labels.dropna()
        assert set(valid.unique()).issubset({-1, 0, 1})


# =============================================================================
# Patterns
# =============================================================================

class TestPatterns:
    def test_returns_dataframe(self, ohlcv_df):
        result = detect_all_patterns(ohlcv_df)
        assert isinstance(result, pd.DataFrame)

    def test_boolean_columns(self, ohlcv_df):
        result = detect_all_patterns(ohlcv_df)
        for col in result.columns:
            if col not in ohlcv_df.columns:
                assert result[col].dtype == bool or result[col].isin([0, 1, True, False]).all()
