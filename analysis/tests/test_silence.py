"""Tests for the 4-condition SilenceRule."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.confidence.silence import SilenceRule, compute_z_scores
from src.ml.confidence.maturity import MaturityGate


@pytest.fixture
def rule():
    return SilenceRule()


@pytest.fixture
def mature_gate():
    g = MaturityGate()
    for _ in range(200):
        g.record_sample()
    return g


class TestColdStart:
    def test_cold_start_triggers_silence(self, rule):
        gate = MaturityGate()
        for _ in range(5):
            gate.record_sample()
        silent, reason = rule.should_stay_silent(gate, 0.90, 3, 0)
        assert silent is True
        assert "cold_start" in reason


class TestLowConfidence:
    def test_low_confidence_triggers_silence(self, rule, mature_gate):
        silent, reason = rule.should_stay_silent(mature_gate, 0.30, 5, 1)
        assert silent is True
        assert "low_confidence" in reason


class TestNeutralDeviation:
    def test_neutral_deviation_triggers_silence(self, rule, mature_gate):
        z_scores = {"rsi": 0.3, "adx": -0.5, "cci": 0.1}
        silent, reason = rule.should_stay_silent(
            mature_gate, 0.80, 3, 0, feature_z_scores=z_scores
        )
        assert silent is True
        assert "neutral_deviation" in reason


class TestConflictingSignals:
    def test_conflicting_signals_triggers_silence(self, rule, mature_gate):
        # Strong z-scores to avoid neutral deviation, but conflicting counts
        z_scores = {"rsi": 2.5}
        silent, reason = rule.should_stay_silent(
            mature_gate, 0.80, 3, 3, feature_z_scores=z_scores
        )
        assert silent is True
        assert "conflicting_signals" in reason


class TestNoSilence:
    def test_no_silence_when_conditions_clear(self, rule, mature_gate):
        z_scores = {"rsi": 2.5, "adx": 1.5}
        silent, reason = rule.should_stay_silent(
            mature_gate, 0.85, 5, 1, feature_z_scores=z_scores
        )
        assert silent is False
        assert reason == ""


class TestIndependence:
    def test_each_condition_independent(self, rule):
        """Only one condition true → still silent."""
        gate = MaturityGate()
        gate.record_sample()  # only 1 sample → cold start
        # But confidence is high, z-scores strong, signals clear
        z_scores = {"rsi": 3.0}
        silent, reason = rule.should_stay_silent(
            gate, 0.95, 5, 0, feature_z_scores=z_scores
        )
        assert silent is True
        assert "cold_start" in reason


class TestZScoreComputation:
    def test_compute_z_scores(self):
        values = {"rsi": 80.0, "adx": 30.0}
        means = {"rsi": 50.0, "adx": 25.0}
        stds = {"rsi": 10.0, "adx": 5.0}
        z = compute_z_scores(values, means, stds)
        assert z["rsi"] == pytest.approx(3.0)
        assert z["adx"] == pytest.approx(1.0)
