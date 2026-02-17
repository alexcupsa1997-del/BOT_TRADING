"""
Maturity Gating System — 3-Tier Confidence Ceiling

Prevents a newly deployed model from expressing full confidence until
it has accumulated enough live data. Directly transfers AI_BIOPSY.md §8.1.

Tiers:
    CALIBRATING  (0-49 samples)   → max 50% confidence
    LEARNING     (50-199 samples) → max 80% confidence
    MATURE       (200+ samples)   → full confidence passthrough

Includes the "10/10 prerequisite rule": the system must retrain
every 10 samples until mature.
"""

from enum import Enum


class MaturityTier(Enum):
    CALIBRATING = "calibrating"
    LEARNING = "learning"
    MATURE = "mature"


TIER_CEILINGS = {
    MaturityTier.CALIBRATING: 0.50,
    MaturityTier.LEARNING: 0.80,
    MaturityTier.MATURE: 1.00,
}

TIER_THRESHOLDS = {
    MaturityTier.CALIBRATING: 0,
    MaturityTier.LEARNING: 50,
    MaturityTier.MATURE: 200,
}


class MaturityGate:
    """Gates raw model confidence through a maturity ceiling."""

    def __init__(self):
        self.samples_seen: int = 0
        self.tier: MaturityTier = MaturityTier.CALIBRATING
        self._retrain_counter: int = 0

    def record_sample(self) -> bool:
        """
        Record one observed sample.

        Returns:
            True if a retrain should be triggered (every 10 samples
            while not yet mature — the 10/10 prerequisite rule).
        """
        self.samples_seen += 1
        self._retrain_counter += 1
        self._update_tier()

        if self.tier != MaturityTier.MATURE and self._retrain_counter >= 10:
            self._retrain_counter = 0
            return True
        return False

    def gate(self, raw_confidence: float) -> float:
        """Apply the maturity ceiling to a raw confidence score."""
        ceiling = TIER_CEILINGS[self.tier]
        return min(raw_confidence, ceiling)

    def reset(self):
        """Reset to CALIBRATING (e.g., after a model retrain)."""
        self.samples_seen = 0
        self.tier = MaturityTier.CALIBRATING
        self._retrain_counter = 0

    def _update_tier(self):
        if self.samples_seen >= TIER_THRESHOLDS[MaturityTier.MATURE]:
            self.tier = MaturityTier.MATURE
        elif self.samples_seen >= TIER_THRESHOLDS[MaturityTier.LEARNING]:
            self.tier = MaturityTier.LEARNING
        else:
            self.tier = MaturityTier.CALIBRATING
