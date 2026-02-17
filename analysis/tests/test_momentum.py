"""Tests for the MomentumTracker."""

import pytest
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.reasoning.momentum import MomentumTracker


@pytest.fixture
def tracker():
    return MomentumTracker()


class TestInitialState:
    def test_initial_momentum_is_neutral(self, tracker):
        assert tracker.momentum == 1.0
        assert not tracker.is_tilted
        assert not tracker.is_hot


class TestWinStreak:
    def test_five_wins_increases_momentum(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(True, t + timedelta(minutes=i))
        assert tracker.momentum > 1.2

    def test_is_hot_after_wins(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(True, t + timedelta(minutes=i))
        assert tracker.is_hot is True


class TestLossStreak:
    def test_five_losses_decreases_momentum(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(False, t + timedelta(minutes=i))
        assert tracker.momentum < 0.85

    def test_is_tilted_after_losses(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(False, t + timedelta(minutes=i))
        assert tracker.is_tilted is True


class TestPositionSizing:
    def test_position_size_halved_when_tilted(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(False, t + timedelta(minutes=i))
        assert tracker.is_tilted
        assert tracker.adjust_position_size(1.0) == 0.5

    def test_position_size_boosted_when_hot(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(True, t + timedelta(minutes=i))
        assert tracker.is_hot
        assert tracker.adjust_position_size(1.0) == 1.25


class TestTimeDecay:
    def test_time_decay_reduces_momentum(self, tracker):
        t1 = datetime(2024, 1, 1, 12, 0)
        for i in range(5):
            tracker.record_trade(True, t1 + timedelta(minutes=i))
        high_momentum = tracker.momentum

        # Large time gap (24 hours)
        t2 = t1 + timedelta(hours=24)
        tracker.record_trade(True, t2)
        # After time decay + one win, momentum should be lower than peak
        assert tracker.momentum < high_momentum


class TestClamping:
    def test_clamping_prevents_extreme_values(self, tracker):
        t = datetime(2024, 1, 1, 12, 0)
        # Many wins
        for i in range(20):
            tracker.record_trade(True, t + timedelta(minutes=i))
        assert tracker.momentum <= 1.4

        # Many losses
        tracker2 = MomentumTracker()
        for i in range(20):
            tracker2.record_trade(False, t + timedelta(minutes=i))
        assert tracker2.momentum >= 0.7
