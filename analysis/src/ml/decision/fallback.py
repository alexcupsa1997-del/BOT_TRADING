"""
4-Tier Fallback Decision Engine

Guarantees the system never returns nothing. Each tier degrades gracefully.
Transfers AI_BIOPSY.md §8.2 "COPER → Hybrid ML+RAG → RAG Basic → Template."

Trading tiers:
    1. COPER:        Episodic memory retrieval (best if effective)
    2. ML_MODEL:     TradingBrain forward pass + maturity/drift/silence
    3. SIGNALS:      Weighted signal aggregation (existing pipeline)
    4. CONSERVATIVE:  Minimal exposure, HOLD — always returns something
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

import torch


class FallbackTier(IntEnum):
    COPER = 1
    ML_MODEL = 2
    SIGNALS = 3
    CONSERVATIVE = 4


@dataclass
class FallbackDecision:
    """Decision output from the fallback engine."""
    action: str                 # "LONG" | "SHORT" | "HOLD"
    confidence: float           # 0-1
    source_tier: FallbackTier
    reasoning: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_size_pct: float = 0.0


class FallbackDecisionEngine:
    """
    Cascading decision engine with graceful degradation.

    All components are optional — the engine works with whatever is available
    and falls through to the next tier when a component is missing or declines.
    """

    def __init__(self, coper=None, brain=None, maturity=None,
                 silence=None, drift=None):
        """
        Args:
            coper:    COPERBank instance (or None to skip Tier 1).
            brain:    TradingBrain nn.Module (or None to skip Tier 2).
            maturity: MaturityGate instance (or None).
            silence:  SilenceRule instance (or None).
            drift:    DriftDetector instance (or None).
        """
        self.coper = coper
        self.brain = brain
        self.maturity = maturity
        self.silence = silence
        self.drift = drift

    def decide(self, market_state: Optional[Dict[str, float]] = None,
               features_tensor: Optional[torch.Tensor] = None,
               indicators_tensor: Optional[torch.Tensor] = None,
               vol_tensor: Optional[torch.Tensor] = None,
               agg_confidence: float = 0.0,
               agg_direction: str = "HOLD",
               bullish_count: int = 0,
               bearish_count: int = 0,
               feature_z_scores: Optional[Dict[str, float]] = None,
               current_price: float = 0.0,
               atr: float = 0.0) -> FallbackDecision:
        """
        Run the 4-tier fallback cascade.

        Returns a FallbackDecision with the source tier labeled.
        """
        # Tier 1: COPER
        if self.coper is not None and market_state is not None:
            result = self._try_coper(market_state)
            if result is not None:
                return result

        # Tier 2: ML Model
        if self.brain is not None and features_tensor is not None:
            result = self._try_ml(
                features_tensor, indicators_tensor, vol_tensor,
                bullish_count, bearish_count, feature_z_scores,
                agg_confidence, current_price, atr,
            )
            if result is not None:
                return result

        # Tier 3: Signal Aggregation
        if agg_confidence > 0.40 and agg_direction != "HOLD":
            return self._from_signals(
                agg_direction, agg_confidence, current_price, atr
            )

        # Tier 4: Conservative Default
        return self._conservative_default(current_price, atr)

    def _try_coper(self, market_state: Dict[str, float]) -> Optional[FallbackDecision]:
        try:
            similar = self.coper.retrieve(market_state, k=5)
            if not similar:
                return None
            best = max(similar, key=lambda e: e.effectiveness)
            if best.effectiveness > 0.7:
                return FallbackDecision(
                    action=best.decision,
                    confidence=best.effectiveness,
                    source_tier=FallbackTier.COPER,
                    reasoning=f"COPER: similar experience (eff={best.effectiveness:.2f})",
                )
        except Exception:
            pass
        return None

    def _try_ml(self, features_tensor, indicators_tensor, vol_tensor,
                bullish_count, bearish_count, feature_z_scores,
                agg_confidence, current_price, atr) -> Optional[FallbackDecision]:
        try:
            with torch.no_grad():
                out = self.brain(features_tensor, indicators_tensor, vol_tensor)

            raw_conf = out.confidence.squeeze().item()

            # Apply maturity gating
            gated_conf = raw_conf
            if self.maturity is not None:
                gated_conf = self.maturity.gate(raw_conf)

            # Apply drift adjustment
            if self.drift is not None:
                gated_conf = self.drift.adjust_confidence(gated_conf)

            # Check silence
            if self.silence is not None and self.maturity is not None:
                silent, reason = self.silence.should_stay_silent(
                    self.maturity, gated_conf,
                    bullish_count, bearish_count, feature_z_scores,
                )
                if silent:
                    return None

            if gated_conf > 0.5:
                direction_idx = out.direction.squeeze().argmax().item()
                action = ["SHORT", "HOLD", "LONG"][direction_idx]
                sl = current_price - atr * 1.5 if action == "LONG" else current_price + atr * 1.5
                tp = current_price + atr * 3.0 if action == "LONG" else current_price - atr * 3.0
                return FallbackDecision(
                    action=action,
                    confidence=gated_conf,
                    source_tier=FallbackTier.ML_MODEL,
                    reasoning=f"ML: direction={action}, conf={gated_conf:.2f}",
                    entry_price=current_price,
                    stop_loss=sl if action != "HOLD" else 0.0,
                    take_profit=tp if action != "HOLD" else 0.0,
                    position_size_pct=0.03 if action != "HOLD" else 0.0,
                )
        except Exception:
            pass
        return None

    def _from_signals(self, direction: str, confidence: float,
                      current_price: float, atr: float) -> FallbackDecision:
        action = direction if direction in ("LONG", "SHORT") else "HOLD"
        conf = confidence / 100.0 if confidence > 1.0 else confidence
        sl = current_price - atr * 1.5 if action == "LONG" else current_price + atr * 1.5
        tp = current_price + atr * 3.0 if action == "LONG" else current_price - atr * 3.0
        return FallbackDecision(
            action=action,
            confidence=conf,
            source_tier=FallbackTier.SIGNALS,
            reasoning=f"Signals: {action} @ {conf:.2f}",
            entry_price=current_price,
            stop_loss=sl if action != "HOLD" else 0.0,
            take_profit=tp if action != "HOLD" else 0.0,
            position_size_pct=0.02 if action != "HOLD" else 0.0,
        )

    def _conservative_default(self, current_price: float,
                              atr: float) -> FallbackDecision:
        return FallbackDecision(
            action="HOLD",
            confidence=0.0,
            source_tier=FallbackTier.CONSERVATIVE,
            reasoning="Conservative: no actionable signal",
            entry_price=current_price,
            position_size_pct=0.0,
        )
