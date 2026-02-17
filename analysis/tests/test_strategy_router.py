"""Tests for StrategyRouter (Fase 4)."""

import pytest

from src.quant.market_regime import Regime
from src.quant.strategy_router import (
    StrategyRouter, StrategyRouterConfig, DEFAULT_REGIME_MAP,
)
from src.quant.strategies.base_strategy import BaseStrategy


class TestStrategyRouter:
    def test_default_mapping(self):
        router = StrategyRouter()
        mappings = router.get_all_mappings()
        assert mappings["TRENDING"] == "trend_following"
        assert mappings["RANGING"] == "mean_reversion"
        assert mappings["VOLATILE"] == "breakout"
        assert mappings["LOW_VOL"] == "grid_market_making"

    def test_get_strategy_returns_base_strategy(self):
        router = StrategyRouter()
        for regime in Regime:
            strategy = router.get_strategy(regime)
            assert isinstance(strategy, BaseStrategy)

    def test_strategy_caching(self):
        router = StrategyRouter()
        s1 = router.get_strategy(Regime.TRENDING)
        s2 = router.get_strategy(Regime.TRENDING)
        assert s1 is s2  # same instance

    def test_set_mapping_override(self):
        router = StrategyRouter()
        router.set_mapping(Regime.TRENDING, "breakout")
        strategy = router.get_strategy(Regime.TRENDING)
        assert strategy.name == "breakout"

    def test_set_mapping_invalid_raises(self):
        router = StrategyRouter()
        with pytest.raises(ValueError, match="Unknown strategy"):
            router.set_mapping(Regime.TRENDING, "nonexistent_strategy")

    def test_get_model_weights(self):
        router = StrategyRouter()
        weights = router.get_model_weights(Regime.TRENDING)
        assert "bilstm" in weights
        assert weights["bilstm"] > 1.0  # boosted in trending

    def test_custom_config(self):
        config = StrategyRouterConfig(
            regime_map={
                Regime.TRENDING: "breakout",
                Regime.RANGING: "trend_following",
                Regime.VOLATILE: "mean_reversion",
                Regime.LOW_VOL: "grid_market_making",
            }
        )
        router = StrategyRouter(config)
        assert router.get_strategy(Regime.TRENDING).name == "breakout"
        assert router.get_strategy(Regime.RANGING).name == "trend_following"

    def test_strategy_names_match_preferred_regimes(self):
        router = StrategyRouter()
        for regime in Regime:
            strategy = router.get_strategy(regime)
            # Each default strategy's preferred_regime should match
            regime_name = {
                Regime.TRENDING: "TRENDING",
                Regime.RANGING: "RANGING",
                Regime.VOLATILE: "VOLATILE",
                Regime.LOW_VOL: "LOW_VOL",
            }[regime]
            assert strategy.preferred_regime == regime_name
