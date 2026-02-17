"""Tests for the DriftDetector."""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.confidence.drift import DriftDetector


@pytest.fixture
def detector():
    """Detector with baseline set from well-behaved training data."""
    d = DriftDetector(window_size=50)
    np.random.seed(42)
    preds = np.random.normal(0.5, 0.1, size=200)
    features = {
        "rsi": np.random.uniform(30, 70, size=200),
        "adx": np.random.uniform(10, 50, size=200),
    }
    d.set_baseline(preds, features)
    return d


class TestNoDrift:
    def test_no_drift_when_distribution_unchanged(self, detector):
        np.random.seed(42)
        for _ in range(50):
            detector.record_prediction(
                np.random.normal(0.5, 0.1),
                {"rsi": np.random.uniform(30, 70), "adx": np.random.uniform(10, 50)},
            )
        assert detector.combined_drift() < 0.8


class TestStatDrift:
    def test_detects_mean_shift(self, detector):
        # Feed predictions with mean shifted by 50% (0.5 → 0.75)
        for _ in range(50):
            detector.record_prediction(0.75)
        stat = detector.detect_stat_drift()
        assert stat > 0.5


class TestDistributionDrift:
    def test_detects_feature_shift(self, detector):
        # Feed features completely out of training range
        for _ in range(50):
            detector.record_prediction(
                0.5,
                {"rsi": np.random.uniform(80, 100), "adx": np.random.uniform(80, 100)},
            )
        dist = detector.detect_distribution_drift()
        assert dist > 0.3


class TestConfidenceAdjustment:
    def test_reduces_on_drift(self, detector):
        # Inject drift
        for _ in range(50):
            detector.record_prediction(0.9, {"rsi": 95.0, "adx": 95.0})
        adjusted = detector.adjust_confidence(0.8)
        assert adjusted < 0.8

    def test_floors_at_50_percent(self, detector):
        # Max drift scenario
        for _ in range(50):
            detector.record_prediction(10.0, {"rsi": 999.0, "adx": 999.0})
        adjusted = detector.adjust_confidence(0.8)
        assert adjusted >= 0.8 * 0.5  # Floor at 50% of raw


class TestRetrain:
    def test_should_retrain_on_extreme_drift(self):
        d = DriftDetector(window_size=50, retrain_threshold=0.5)
        np.random.seed(42)
        preds = np.random.normal(0.5, 0.1, size=200)
        features = {"rsi": np.random.uniform(30, 70, size=200)}
        d.set_baseline(preds, features)
        for _ in range(50):
            d.record_prediction(10.0, {"rsi": 999.0})
        assert d.should_retrain() is True
