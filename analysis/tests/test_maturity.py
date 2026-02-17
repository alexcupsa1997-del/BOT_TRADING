"""Tests for the 3-tier MaturityGate."""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.confidence.maturity import MaturityGate, MaturityTier


@pytest.fixture
def gate():
    return MaturityGate()


class TestTierProgression:
    def test_initial_tier_is_calibrating(self, gate):
        assert gate.tier == MaturityTier.CALIBRATING
        assert gate.samples_seen == 0

    def test_gate_caps_at_50_during_calibrating(self, gate):
        assert gate.gate(0.95) == 0.50

    def test_gate_caps_at_80_during_learning(self, gate):
        for _ in range(50):
            gate.record_sample()
        assert gate.tier == MaturityTier.LEARNING
        assert gate.gate(0.95) == 0.80

    def test_gate_passes_through_at_mature(self, gate):
        for _ in range(200):
            gate.record_sample()
        assert gate.tier == MaturityTier.MATURE
        assert gate.gate(0.95) == 0.95

    def test_gate_does_not_exceed_raw_value(self, gate):
        for _ in range(200):
            gate.record_sample()
        assert gate.gate(0.30) == 0.30


class TestRetrainSignal:
    def test_retrain_signal_every_10_samples(self, gate):
        signals = []
        for i in range(30):
            signals.append(gate.record_sample())
        # Retrain on the 10th and 20th sample
        assert signals[9] is True
        assert signals[19] is True

    def test_no_retrain_signal_when_mature(self, gate):
        # Get to mature
        for _ in range(200):
            gate.record_sample()
        # No more retrain signals
        for _ in range(20):
            assert gate.record_sample() is False


class TestReset:
    def test_reset_returns_to_calibrating(self, gate):
        for _ in range(100):
            gate.record_sample()
        assert gate.tier == MaturityTier.LEARNING
        gate.reset()
        assert gate.tier == MaturityTier.CALIBRATING
        assert gate.samples_seen == 0
        assert gate.gate(0.95) == 0.50
