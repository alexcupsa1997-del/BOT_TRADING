"""Tests for the 4-Tier FallbackDecisionEngine."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.decision.fallback import (
    FallbackDecisionEngine, FallbackDecision, FallbackTier,
)
from src.ml.memory.coper import COPERBank, create_experience


@pytest.fixture
def empty_engine():
    """Engine with no components — always falls to Tier 4."""
    return FallbackDecisionEngine()


class TestTier4Conservative:
    def test_always_returns_valid_decision(self, empty_engine):
        result = empty_engine.decide()
        assert isinstance(result, FallbackDecision)
        assert result.source_tier == FallbackTier.CONSERVATIVE

    def test_conservative_default_is_hold(self, empty_engine):
        result = empty_engine.decide()
        assert result.action == "HOLD"
        assert result.confidence == 0.0


class TestTier1COPER:
    def test_coper_used_when_effective(self):
        bank = COPERBank()
        state = {"rsi": 30.0, "adx": 40.0, "volatility": 0.02}
        exp = create_experience(state, "LONG", 1800, 1820, "XAUUSD", "H1")
        exp.effectiveness = 0.9  # High effectiveness
        bank.store(exp)

        engine = FallbackDecisionEngine(coper=bank)
        result = engine.decide(market_state=state)
        assert result.source_tier == FallbackTier.COPER
        assert result.action == "LONG"


class TestTier3Signals:
    def test_signals_used_when_confident(self):
        engine = FallbackDecisionEngine()
        result = engine.decide(
            agg_confidence=0.75,
            agg_direction="LONG",
            current_price=1800.0,
            atr=5.0,
        )
        assert result.source_tier == FallbackTier.SIGNALS
        assert result.action == "LONG"

    def test_signals_skipped_when_low_confidence(self):
        engine = FallbackDecisionEngine()
        result = engine.decide(
            agg_confidence=0.20,
            agg_direction="LONG",
        )
        assert result.source_tier == FallbackTier.CONSERVATIVE


class TestSourceTierLabeled:
    def test_source_tier_labeled_correctly(self):
        engine = FallbackDecisionEngine()
        # No COPER, no ML, low confidence → Tier 4
        result = engine.decide()
        assert result.source_tier == FallbackTier.CONSERVATIVE
        assert result.source_tier.value == 4


class TestNoneComponents:
    def test_none_components_skip_gracefully(self):
        """Engine with coper=None, brain=None should skip to signals or conservative."""
        engine = FallbackDecisionEngine(coper=None, brain=None)
        result = engine.decide(
            market_state={"rsi": 50.0},
            agg_confidence=0.80,
            agg_direction="SHORT",
            current_price=1800.0,
            atr=5.0,
        )
        # Should use Tier 3 (signals) since COPER and ML are None
        assert result.source_tier == FallbackTier.SIGNALS
        assert result.action == "SHORT"
