"""
Silence Rule — 4-Condition Output Suppression

"Prefer no trade over bad trade." (AI_BIOPSY_PART2.md §3.8)

Four independent conditions, any of which triggers silence:
    1. Cold Start:        maturity < 10 samples
    2. Low Confidence:    gated confidence < 40%
    3. Neutral Deviation: all indicator z-scores within ±1.0
    4. Conflicting Signals: bullish ≈ bearish count
"""

from typing import Dict, Tuple, Optional

from .maturity import MaturityGate, MaturityTier


class SilenceRule:
    """Checks whether the system should stay silent (not trade)."""

    def should_stay_silent(
        self,
        maturity_gate: MaturityGate,
        gated_confidence: float,
        bullish_count: int,
        bearish_count: int,
        feature_z_scores: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluate all 4 silence conditions.

        Args:
            maturity_gate: Current maturity gate instance.
            gated_confidence: Confidence after maturity gating (0-1).
            bullish_count: Number of bullish signals.
            bearish_count: Number of bearish signals.
            feature_z_scores: Dict of {indicator: z-score}. Optional.

        Returns:
            (should_be_silent, reason_string)
        """
        # Condition 1: Cold Start
        if (maturity_gate.tier == MaturityTier.CALIBRATING
                and maturity_gate.samples_seen < 10):
            return True, "cold_start: insufficient training data"

        # Condition 2: Low Confidence
        if gated_confidence < 0.40:
            return True, "low_confidence: gated confidence below 40%"

        # Condition 3: Neutral Deviation
        if feature_z_scores:
            all_neutral = all(abs(z) < 1.0 for z in feature_z_scores.values())
            if all_neutral:
                return True, "neutral_deviation: no indicator strongly deviates"

        # Condition 4: Conflicting Signals
        if bullish_count > 0 and bearish_count > 0:
            if abs(bullish_count - bearish_count) <= 1:
                return True, "conflicting_signals: bull/bear signals nearly equal"

        return False, ""


def compute_z_scores(values: Dict[str, float],
                     means: Dict[str, float],
                     stds: Dict[str, float]) -> Dict[str, float]:
    """
    Compute z-scores for a set of indicator values.

    Args:
        values: Current indicator values.
        means:  Rolling mean per indicator.
        stds:   Rolling std per indicator.

    Returns:
        Dict of {indicator: z_score}.
    """
    z_scores = {}
    for name, val in values.items():
        mean = means.get(name, 0.0)
        std = max(stds.get(name, 1.0), 0.01)
        z_scores[name] = (val - mean) / std
    return z_scores
