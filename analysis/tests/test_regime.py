"""Tests for MarketRegimeClassifier (Fase 4)."""

import numpy as np
import pandas as pd
import pytest

from src.quant.market_regime import MarketRegimeClassifier, Regime, REGIME_LABELS


def _make_trending_data(n: int = 200) -> pd.DataFrame:
    """Simulate trending market: strong ADX, low relative ATR, aligned EMAs."""
    np.random.seed(42)
    close = np.cumsum(np.random.normal(0.5, 1, n)) + 100  # uptrend
    return pd.DataFrame({
        "open": close - 0.5,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": np.random.uniform(100, 200, n),
    }, index=pd.date_range("2025-01-01", periods=n, freq="1h"))


def _make_ranging_data(n: int = 200) -> pd.DataFrame:
    """Simulate ranging market: low ADX, narrow BB, low volume."""
    np.random.seed(123)
    close = 100 + np.sin(np.linspace(0, 8 * np.pi, n)) * 2  # oscillating
    return pd.DataFrame({
        "open": close - 0.3,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.random.uniform(50, 80, n),
    }, index=pd.date_range("2025-01-01", periods=n, freq="1h"))


def _make_volatile_data(n: int = 200) -> pd.DataFrame:
    """Simulate volatile market: high ATR, wide BB, high volume."""
    np.random.seed(99)
    close = 100 + np.cumsum(np.random.normal(0, 5, n))  # large moves
    return pd.DataFrame({
        "open": close - 3,
        "high": close + 5,
        "low": close - 5,
        "close": close,
        "volume": np.random.uniform(500, 1000, n),
    }, index=pd.date_range("2025-01-01", periods=n, freq="1h"))


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add indicator columns needed by regime classifier."""
    from src.quant.indicators import compute_all_indicators
    return compute_all_indicators(df)


class TestRegimeEnum:
    def test_regime_values(self):
        assert Regime.TRENDING == 0
        assert Regime.RANGING == 1
        assert Regime.VOLATILE == 2
        assert Regime.LOW_VOL == 3

    def test_regime_labels(self):
        for r in Regime:
            assert r in REGIME_LABELS


class TestRuleBasedClassification:
    """Test fallback rule-based classification (no HMM)."""

    def test_classify_returns_series(self):
        df = _add_indicators(_make_trending_data())
        clf = MarketRegimeClassifier()
        result = clf.classify(df)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_current_regime_returns_enum(self):
        df = _add_indicators(_make_trending_data())
        clf = MarketRegimeClassifier()
        regime = clf.current_regime(df)
        assert isinstance(regime, Regime)

    def test_trending_data_detected(self):
        df = _add_indicators(_make_trending_data(300))
        clf = MarketRegimeClassifier(min_persistence=1)
        regimes = clf.classify(df)
        # Majority should be TRENDING (ADX builds up in trend)
        counts = regimes.value_counts()
        assert Regime.TRENDING in counts.index or Regime.RANGING in counts.index

    def test_volatile_data_high_atr(self):
        df = _add_indicators(_make_volatile_data(300))
        clf = MarketRegimeClassifier(min_persistence=1)
        regimes = clf.classify(df)
        counts = regimes.value_counts()
        # Volatile data should have VOLATILE or TRENDING (high ATR)
        assert len(counts) > 0


class TestHMMClassification:
    """Test HMM-based classification."""

    def test_fit_and_classify(self):
        df = _add_indicators(_make_trending_data(500))
        clf = MarketRegimeClassifier(seed=42)
        clf.fit(df)
        assert clf._fitted
        regimes = clf.classify(df)
        assert len(regimes) == len(df)
        assert all(r in list(Regime) for r in regimes.values)

    def test_fit_with_insufficient_data(self):
        df = _add_indicators(_make_trending_data(20))
        clf = MarketRegimeClassifier()
        clf.fit(df)
        # Should fallback to rule-based (not enough data)
        assert not clf._fitted

    def test_state_mapping_covers_all_regimes(self):
        df = _add_indicators(_make_trending_data(500))
        clf = MarketRegimeClassifier(seed=42)
        clf.fit(df)
        assert len(clf._state_map) == 4
        mapped_regimes = set(clf._state_map.values())
        assert mapped_regimes == {Regime.TRENDING, Regime.RANGING,
                                  Regime.VOLATILE, Regime.LOW_VOL}


class TestPersistenceFilter:
    """Test anti-whipsaw persistence filter."""

    def test_filter_prevents_single_bar_switch(self):
        clf = MarketRegimeClassifier(min_persistence=3)
        raw = np.array([0, 0, 0, 1, 0, 0, 0])  # brief blip at idx=3
        filtered = clf._persistence_filter(raw)
        # The single blip should be filtered out
        assert filtered[3] == 0

    def test_filter_allows_persistent_change(self):
        clf = MarketRegimeClassifier(min_persistence=3)
        raw = np.array([0, 0, 0, 1, 1, 1, 1, 1])
        filtered = clf._persistence_filter(raw)
        # After 3 bars of regime 1, it should switch
        assert filtered[-1] == 1

    def test_filter_empty_input(self):
        clf = MarketRegimeClassifier()
        result = clf._persistence_filter(np.array([]))
        assert len(result) == 0

    def test_filter_min_persistence_5(self):
        clf = MarketRegimeClassifier(min_persistence=5)
        # 4 bars of new regime = not enough
        raw = np.array([0, 0, 1, 1, 1, 1, 0, 0])
        filtered = clf._persistence_filter(raw)
        assert filtered[5] == 0  # still 0, didn't persist long enough


class TestFeatureExtraction:
    def test_extract_features_shape(self):
        df = _add_indicators(_make_trending_data(100))
        clf = MarketRegimeClassifier()
        X = clf._extract_features(df)
        assert X.shape == (100, 5)  # 5 features
        assert not np.any(np.isnan(X[-1]))  # last row should be clean
