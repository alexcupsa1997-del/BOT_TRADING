"""
Feature Registry — Strict Feature Vector Contract

Enforces a fixed-dimension feature vector contract between the quant pipeline
and ML models. Inspired by CS2's METADATA_DIM=19 pattern (AI_BIOPSY.md §6.1).

Every feature has a defined name, dtype, valid range, and category.
When any component adds or removes a feature, the contract breaks loudly
at validation time — not silently at inference time.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FeatureSpec:
    """Specification for a single feature in the vector."""
    name: str
    dtype: str                          # "float32" | "bool"
    valid_range: Tuple[float, float]    # (min, max) for clamping
    category: str                       # "indicator" | "pattern" | "channel" | "sr"
    required: bool = True
    default: float = 0.0


class FeatureRegistry:
    """
    Singleton registry enforcing a strict feature vector contract.

    Usage:
        registry = FeatureRegistry.get_instance()
        registry.validate_parity(feature_names)   # raises ValueError if missing
        validated = registry.validate_values(fd)   # clamps out-of-range values
    """
    _instance: Optional['FeatureRegistry'] = None

    @classmethod
    def get_instance(cls) -> 'FeatureRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def __init__(self):
        self._schema: Dict[str, FeatureSpec] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register the 29 default features matching neural_decision.py."""
        # Indicator features (9)
        indicator_ranges = [
            ("ind_rsi", (0, 100)),
            ("ind_stoch_k", (0, 100)),
            ("ind_stoch_d", (0, 100)),
            ("ind_cci", (0, 100)),
            ("ind_adx", (0, 100)),
            ("ind_atr", (0, 100)),
            ("ind_bb_position", (0, 100)),
            ("ind_macd_diff", (0, 100)),
            ("ind_macd_momentum", (0, 100)),
        ]
        for name, (lo, hi) in indicator_ranges:
            self.register(FeatureSpec(name, "float32", (lo, hi), "indicator"))

        # Pattern features (8)
        patterns = [
            "doji", "hammer", "engulfing_bullish", "engulfing_bearish",
            "morning_star", "evening_star", "double_top", "double_bottom",
        ]
        for pat in patterns:
            self.register(FeatureSpec(f"pat_{pat}", "bool", (0, 100), "pattern"))

        # Channel features (4)
        for ch in ["chan_ascending", "chan_descending", "chan_horizontal"]:
            self.register(FeatureSpec(ch, "bool", (0, 100), "channel"))
        self.register(FeatureSpec("chan_position", "float32", (0, 100), "channel"))

        # S/R features (2)
        self.register(FeatureSpec("sr_support_dist", "float32", (0, 100), "sr"))
        self.register(FeatureSpec("sr_resistance_dist", "float32", (0, 100), "sr"))

        # Smart Money features (6)
        for smc in ["smc_bullish_fvg", "smc_bearish_fvg"]:
            self.register(FeatureSpec(smc, "bool", (0, 100), "smart_money"))
        self.register(FeatureSpec("smc_fvg_distance", "float32", (0, 100), "smart_money"))
        for smc in ["smc_bos_bullish", "smc_bos_bearish"]:
            self.register(FeatureSpec(smc, "bool", (0, 100), "smart_money"))
        self.register(FeatureSpec("smc_confluence", "float32", (0, 100), "smart_money"))

    def register(self, spec: FeatureSpec):
        """Add a feature to the schema."""
        self._schema[spec.name] = spec

    def validate_parity(self, feature_names: List[str]) -> bool:
        """
        Check that all required features are present.

        Raises:
            ValueError: If any required feature is missing.
        """
        required = {n for n, s in self._schema.items() if s.required}
        provided = set(feature_names)
        missing = required - provided
        if missing:
            raise ValueError(f"Feature parity violation: missing {sorted(missing)}")
        return True

    def validate_values(self, feature_dict: Dict[str, float]) -> Dict[str, float]:
        """Clamp feature values to their valid ranges."""
        validated = {}
        for name, value in feature_dict.items():
            spec = self._schema.get(name)
            if spec:
                lo, hi = spec.valid_range
                validated[name] = max(lo, min(hi, value))
            else:
                validated[name] = value
        return validated

    @property
    def expected_dim(self) -> int:
        """Total number of registered features."""
        return len(self._schema)

    def get_ordered_names(self) -> List[str]:
        """Deterministic ordered list of feature names."""
        return list(self._schema.keys())

    def get_spec(self, name: str) -> Optional[FeatureSpec]:
        """Look up a single feature spec by name."""
        return self._schema.get(name)
