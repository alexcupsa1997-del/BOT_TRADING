"""
Momentum Tracker — Win/Loss Streak Position Sizing

Tracks trading momentum (win/loss streaks) and adjusts position sizing.
Transfers AI_BIOPSY_PART2.md §3.4.

Asymmetric update: wins add +0.05, losses subtract -0.04.
~4 wins needed to recover from 3 losses.
Clamped to [0.7, 1.4].
Time decay: momentum decays toward neutral during inactivity.
"""

import math
from datetime import datetime
from typing import List, Optional, Tuple


class MomentumTracker:
    """Tracks win/loss streaks and adjusts position sizing."""

    def __init__(self):
        self.momentum: float = 1.0
        self.last_trade_time: Optional[datetime] = None
        self.trade_history: List[Tuple[datetime, bool]] = []

    def record_trade(self, is_win: bool, timestamp: Optional[datetime] = None):
        """
        Record a trade outcome and update momentum.

        Args:
            is_win: True if the trade was profitable.
            timestamp: When the trade closed. Defaults to now.
        """
        ts = timestamp or datetime.utcnow()

        # Time decay: momentum drifts toward 1.0 during inactivity
        if self.last_trade_time is not None:
            gap_hours = (ts - self.last_trade_time).total_seconds() / 3600.0
            if gap_hours > 0:
                self.momentum *= math.exp(-0.15 * gap_hours)
                # After decay, nudge back toward neutral
                self.momentum = 1.0 + (self.momentum - 1.0) * math.exp(-0.05 * gap_hours)

        # Update momentum
        if is_win:
            self.momentum += 0.05
        else:
            self.momentum -= 0.04

        # Clamp
        self.momentum = max(0.7, min(1.4, self.momentum))

        self.last_trade_time = ts
        self.trade_history.append((ts, is_win))

    @property
    def is_tilted(self) -> bool:
        """True if on a cold streak (momentum < 0.85)."""
        return self.momentum < 0.85

    @property
    def is_hot(self) -> bool:
        """True if on a hot streak (momentum > 1.2)."""
        return self.momentum > 1.2

    def adjust_position_size(self, base_size: float) -> float:
        """
        Scale position size by momentum.

        Args:
            base_size: Base position size (e.g., fraction of capital).

        Returns:
            Adjusted position size.
        """
        if self.is_tilted:
            return base_size * 0.5
        if self.is_hot:
            return base_size * 1.25
        return base_size * self.momentum
