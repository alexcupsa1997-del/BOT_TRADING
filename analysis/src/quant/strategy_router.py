"""
Strategy Router — Maps market regime to optimal strategy.

Selects the strategy best suited for the current market regime
based on configurable mapping. Also provides model weight
multipliers for the ensemble (Fase 3) per regime.

Ref: FUSION_PLAN Fase 4, item 4.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Type

from loguru import logger

from .market_regime import Regime, REGIME_LABELS
from .strategies.base_strategy import BaseStrategy
from .strategies import (
    TrendFollowing, MeanReversion, Breakout, GridMarketMaking,
    STRATEGY_REGISTRY,
)


# Default regime → strategy mapping
DEFAULT_REGIME_MAP: Dict[Regime, str] = {
    Regime.TRENDING: "trend_following",
    Regime.RANGING: "mean_reversion",
    Regime.VOLATILE: "breakout",
    Regime.LOW_VOL: "grid_market_making",
}

# Model weight multipliers per regime (applied to ensemble base weights)
DEFAULT_MODEL_WEIGHTS: Dict[Regime, Dict[str, float]] = {
    Regime.TRENDING: {
        "bilstm": 1.5, "attention_seq2seq": 1.0, "dilated_cnn": 1.0,
        "lstm_attention": 1.0, "lightgbm": 0.8, "xgboost": 0.8,
    },
    Regime.RANGING: {
        "bilstm": 0.8, "attention_seq2seq": 0.8, "dilated_cnn": 0.8,
        "lstm_attention": 0.8, "lightgbm": 1.5, "xgboost": 1.5,
    },
    Regime.VOLATILE: {
        "bilstm": 1.0, "attention_seq2seq": 1.0, "dilated_cnn": 1.5,
        "lstm_attention": 1.0, "lightgbm": 0.8, "xgboost": 0.8,
    },
    Regime.LOW_VOL: {
        "bilstm": 0.5, "attention_seq2seq": 0.5, "dilated_cnn": 0.5,
        "lstm_attention": 0.5, "lightgbm": 1.0, "xgboost": 1.0,
    },
}


@dataclass
class StrategyRouterConfig:
    """Configuration for StrategyRouter."""
    regime_map: Dict[Regime, str] = field(default_factory=lambda: dict(DEFAULT_REGIME_MAP))
    model_weights: Dict[Regime, Dict[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_MODEL_WEIGHTS.items()}
    )


class StrategyRouter:
    """
    Routes market regimes to trading strategies.

    Maintains a cache of instantiated strategy objects for reuse.
    """

    def __init__(self, config: Optional[StrategyRouterConfig] = None):
        cfg = config or StrategyRouterConfig()
        self._regime_map = cfg.regime_map
        self._model_weights = cfg.model_weights
        self._strategy_cache: Dict[str, BaseStrategy] = {}

    def get_strategy(self, regime: Regime) -> BaseStrategy:
        """
        Return the strategy instance for the given regime.

        Strategies are cached after first instantiation.
        """
        name = self._regime_map.get(regime)
        if name is None:
            logger.warning(f"No strategy mapped for regime {REGIME_LABELS.get(regime, regime)}, "
                           f"falling back to mean_reversion")
            name = "mean_reversion"

        if name not in self._strategy_cache:
            cls = STRATEGY_REGISTRY.get(name)
            if cls is None:
                raise ValueError(f"Unknown strategy: {name}. "
                                 f"Available: {list(STRATEGY_REGISTRY.keys())}")
            self._strategy_cache[name] = cls()

        return self._strategy_cache[name]

    def get_model_weights(self, regime: Regime) -> Dict[str, float]:
        """Return model weight multipliers for the given regime."""
        return self._model_weights.get(regime, {})

    def set_mapping(self, regime: Regime, strategy_name: str) -> None:
        """Override the strategy for a specific regime."""
        if strategy_name not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        self._regime_map[regime] = strategy_name
        logger.info(f"Regime {REGIME_LABELS[regime]} → {strategy_name}")

    def get_all_mappings(self) -> Dict[str, str]:
        """Return current regime → strategy mapping as readable dict."""
        return {REGIME_LABELS[r]: name for r, name in self._regime_map.items()}
