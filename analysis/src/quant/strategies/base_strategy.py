"""
Base Strategy ABC for regime-aware trading strategies.

Extends the BacktestEngine.Strategy interface with regime metadata
and standardized signal format.

Ref: FUSION_PLAN Fase 4, item 4.4
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class StrategySignal:
    """Standardized signal output from a strategy."""
    direction: str          # "LONG" | "SHORT"
    tag: str                # Human-readable label (e.g. "ema_ribbon_long")
    strength: float = 1.0   # 0-1, used for sizing / filtering
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_backtest_dict(self) -> Dict[str, Any]:
        """Convert to BacktestEngine-compatible signal dict."""
        return {"direction": self.direction, "tag": self.tag}


class BaseStrategy(ABC):
    """
    Abstract base for all regime-aware trading strategies.

    Compatible with BacktestEngine.Strategy via `on_candle()` interface.
    Strategies receive pre-computed indicator DataFrames and return
    StrategySignal or None.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy name (e.g. 'trend_following')."""
        ...

    @property
    @abstractmethod
    def preferred_regime(self) -> str:
        """Regime where this strategy performs best (e.g. 'TRENDING')."""
        ...

    @abstractmethod
    def on_candle(
        self,
        idx: int,
        row: pd.Series,
        history: pd.DataFrame,
    ) -> Optional[StrategySignal]:
        """
        Evaluate current bar and return a signal or None.

        Args:
            idx: Integer index into the DataFrame.
            row: Current OHLCV row (with indicator columns).
            history: All data up to and including current bar.

        Returns:
            StrategySignal if entry condition met, else None.
        """
        ...

    def on_trade_closed(self, trade) -> None:
        """Optional callback after a trade closes."""
        pass

    def reset(self) -> None:
        """Reset internal state (called between backtests)."""
        pass
