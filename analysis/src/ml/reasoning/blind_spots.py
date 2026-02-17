"""
Blind Spot Detector — Recurring Mistake Detection

Identifies systematic recurring mistakes in trade decisions for
targeted retraining emphasis. Transfers AI_BIOPSY_PART2.md §3.5.

Tracked patterns:
    - late_entry:         Entry > N bars after signal triggered
    - ignored_divergence: RSI/price divergence present but not acted on
    - counter_trend:      Trade direction opposes dominant trend (ADX > 25)
    - oversize_on_tilt:   Position too large when momentum < 0.85
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BlindSpot:
    """A single identified blind spot pattern."""
    pattern: str
    frequency: int = 0
    total_impact: float = 0.0
    examples: List[str] = field(default_factory=list)

    @property
    def avg_impact(self) -> float:
        return self.total_impact / self.frequency if self.frequency > 0 else 0.0

    @property
    def priority(self) -> float:
        return self.frequency * abs(self.avg_impact)


@dataclass
class TradeContext:
    """Context needed to detect blind spots in a trade."""
    trade_id: str
    pnl: float
    entry_delay_bars: int = 0       # Bars between signal and entry
    had_divergence: bool = False    # RSI/price divergence present
    adx_value: float = 0.0         # ADX at entry
    trade_direction: str = "LONG"  # "LONG" | "SHORT"
    trend_direction: str = "UP"    # "UP" | "DOWN" | "FLAT"
    momentum: float = 1.0         # MomentumTracker.momentum at entry
    position_size_pct: float = 0.01


class BlindSpotDetector:
    """Detects and tracks recurring trading mistakes."""

    def __init__(self, late_entry_threshold: int = 3):
        self.blind_spots: Dict[str, BlindSpot] = {}
        self.late_entry_threshold = late_entry_threshold

    def analyze_trade(self, ctx: TradeContext):
        """
        Analyze a completed trade for blind spot patterns.

        Args:
            ctx: Trade context with all relevant metadata.
        """
        # Pattern 1: Late entry
        if ctx.entry_delay_bars > self.late_entry_threshold:
            self._record("late_entry", ctx.pnl, ctx.trade_id)

        # Pattern 2: Ignored divergence
        if ctx.had_divergence and ctx.pnl < 0:
            self._record("ignored_divergence", ctx.pnl, ctx.trade_id)

        # Pattern 3: Counter-trend trade
        if ctx.adx_value > 25:
            is_counter = (
                (ctx.trade_direction == "LONG" and ctx.trend_direction == "DOWN")
                or (ctx.trade_direction == "SHORT" and ctx.trend_direction == "UP")
            )
            if is_counter:
                self._record("counter_trend", ctx.pnl, ctx.trade_id)

        # Pattern 4: Oversize on tilt
        if ctx.momentum < 0.85 and ctx.position_size_pct > 0.03:
            self._record("oversize_on_tilt", ctx.pnl, ctx.trade_id)

    def get_top_blind_spots(self, k: int = 3) -> List[BlindSpot]:
        """Return top-k blind spots by priority (frequency × avg impact)."""
        sorted_spots = sorted(
            self.blind_spots.values(),
            key=lambda b: b.priority,
            reverse=True,
        )
        return sorted_spots[:k]

    def get_retraining_weights(self) -> Dict[str, float]:
        """Map blind spot patterns to relative retraining emphasis weights."""
        if not self.blind_spots:
            return {}
        total_priority = sum(b.priority for b in self.blind_spots.values())
        if total_priority == 0:
            return {name: 1.0 for name in self.blind_spots}
        return {
            name: spot.priority / total_priority
            for name, spot in self.blind_spots.items()
        }

    def _record(self, pattern: str, pnl: float, trade_id: str):
        if pattern not in self.blind_spots:
            self.blind_spots[pattern] = BlindSpot(pattern=pattern)
        spot = self.blind_spots[pattern]
        spot.frequency += 1
        spot.total_impact += pnl
        spot.examples.append(trade_id)
        # Keep only last 5 examples
        if len(spot.examples) > 5:
            spot.examples = spot.examples[-5:]
