"""
Strategy package — Regime-aware trading strategies.

Ref: FUSION_PLAN Fase 4
"""

from .base_strategy import BaseStrategy, StrategySignal
from .trend_following import TrendFollowing
from .mean_reversion import MeanReversion
from .breakout import Breakout
from .grid_market_making import GridMarketMaking

STRATEGY_REGISTRY = {
    "trend_following": TrendFollowing,
    "mean_reversion": MeanReversion,
    "breakout": Breakout,
    "grid_market_making": GridMarketMaking,
}

__all__ = [
    "BaseStrategy", "StrategySignal",
    "TrendFollowing", "MeanReversion", "Breakout", "GridMarketMaking",
    "STRATEGY_REGISTRY",
]
