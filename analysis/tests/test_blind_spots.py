"""Tests for the BlindSpotDetector."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.reasoning.blind_spots import BlindSpotDetector, TradeContext


@pytest.fixture
def detector():
    return BlindSpotDetector()


class TestLateEntry:
    def test_detect_late_entry(self, detector):
        ctx = TradeContext(trade_id="t1", pnl=-10.0, entry_delay_bars=5)
        detector.analyze_trade(ctx)
        assert "late_entry" in detector.blind_spots
        assert detector.blind_spots["late_entry"].frequency == 1


class TestCounterTrend:
    def test_detect_counter_trend(self, detector):
        ctx = TradeContext(
            trade_id="t2", pnl=-15.0,
            adx_value=30.0, trade_direction="LONG", trend_direction="DOWN",
        )
        detector.analyze_trade(ctx)
        assert "counter_trend" in detector.blind_spots


class TestFrequency:
    def test_frequency_increments(self, detector):
        for i in range(3):
            ctx = TradeContext(trade_id=f"t{i}", pnl=-5.0, entry_delay_bars=5)
            detector.analyze_trade(ctx)
        assert detector.blind_spots["late_entry"].frequency == 3


class TestPriorityOrdering:
    def test_priority_ordering(self, detector):
        # High-impact pattern
        for i in range(5):
            ctx = TradeContext(
                trade_id=f"high_{i}", pnl=-20.0,
                adx_value=30.0, trade_direction="LONG", trend_direction="DOWN",
            )
            detector.analyze_trade(ctx)
        # Low-impact pattern
        ctx = TradeContext(trade_id="low_0", pnl=-1.0, entry_delay_bars=5)
        detector.analyze_trade(ctx)

        top = detector.get_top_blind_spots(k=2)
        assert top[0].pattern == "counter_trend"


class TestExamplesCapped:
    def test_examples_capped_at_5(self, detector):
        for i in range(10):
            ctx = TradeContext(trade_id=f"t{i}", pnl=-5.0, entry_delay_bars=5)
            detector.analyze_trade(ctx)
        assert len(detector.blind_spots["late_entry"].examples) == 5
        assert detector.blind_spots["late_entry"].examples[0] == "t5"
