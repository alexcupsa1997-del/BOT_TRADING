"""
TradingOrchestrator — Central Pipeline Coordinator

Wires all components together in the correct dependency order and
provides a single `analyze()` entry point. Inspired by CS2's
AnalysisOrchestrator that runs 6 parallel analysis engines.

Pipeline:
    OHLCV → Indicators → Patterns → Signals → Regime → Strategy → Model → Decision
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import torch

from src.quant.indicators import compute_all_indicators
from src.quant.patterns import detect_all_patterns
from src.quant.signal_processor import (
    extract_indicator_signals, extract_pattern_signals,
    aggregate_signals, AggregatedSignal, SignalDirection,
)
from src.quant.neural_decision import assemble_feature_vector
from src.quant.feature_registry import FeatureRegistry
from src.quant.market_regime import MarketRegimeClassifier, Regime, REGIME_LABELS
from src.quant.strategy_router import StrategyRouter, StrategyRouterConfig
from src.integration.notifier import Notifier, NotifierConfig, NotifyLevel

from src.ml.models.trading_brain import TradingBrain, TradingBrainConfig
from src.ml.models.ensemble_meta_learner import EnsembleMetaLearner, EnsembleConfig
from src.ml.confidence.maturity import MaturityGate
from src.ml.confidence.drift import DriftDetector
from src.ml.confidence.silence import SilenceRule, compute_z_scores
from src.ml.reasoning.momentum import MomentumTracker
from src.ml.reasoning.blind_spots import BlindSpotDetector
from src.ml.memory.coper import COPERBank, create_experience
from src.ml.decision.fallback import (
    FallbackDecisionEngine, FallbackDecision, FallbackTier,
)

from loguru import logger


@dataclass
class OrchestratorConfig:
    """Configuration for the TradingOrchestrator."""
    brain_config: Optional[TradingBrainConfig] = None
    ensemble_config: Optional[EnsembleConfig] = None
    router_config: Optional[StrategyRouterConfig] = None
    notifier_config: Optional[NotifierConfig] = None
    max_coper_size: int = 10000
    drift_window: int = 100
    enable_brain: bool = True
    enable_ensemble: bool = False
    enable_regime: bool = True


class TradingOrchestrator:
    """
    Central orchestration of the full analysis pipeline.
    Coordinates all components in the correct dependency order.
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        cfg = config or OrchestratorConfig()

        self.feature_registry = FeatureRegistry.get_instance()
        self.maturity = MaturityGate()
        self.drift = DriftDetector(window_size=cfg.drift_window)
        self.silence = SilenceRule()
        self.momentum = MomentumTracker()
        self.coper = COPERBank(max_size=cfg.max_coper_size)
        self.blind_spots = BlindSpotDetector()

        # Fase 5: Notifier
        self.notifier = Notifier(cfg.notifier_config)

        # Fase 4: Market Regime + Strategy Router
        self.regime_classifier = MarketRegimeClassifier()
        self.strategy_router = StrategyRouter(cfg.router_config)
        self.enable_regime = cfg.enable_regime
        self._current_regime: Optional[Regime] = None

        # TradingBrain (optional — can run without it)
        self.brain: Optional[TradingBrain] = None
        if cfg.enable_brain and cfg.brain_config is not None:
            self.brain = TradingBrain(cfg.brain_config)
            self.brain.eval()

        # Ensemble (Fase 3 — optional, overrides brain for Tier-2)
        self.ensemble: Optional[EnsembleMetaLearner] = None
        if cfg.enable_ensemble and cfg.ensemble_config is not None:
            self.ensemble = EnsembleMetaLearner(cfg.ensemble_config)

        self.fallback = FallbackDecisionEngine(
            coper=self.coper,
            brain=self.brain,
            maturity=self.maturity,
            silence=self.silence,
            drift=self.drift,
        )

    def set_exchange(self, exchange) -> None:
        """Attach an ExchangeManager for live/paper trading."""
        self._exchange = exchange

    def analyze(self, symbol: str, timeframe: str,
                ohlcv_df: pd.DataFrame) -> FallbackDecision:
        """
        Run the full analysis pipeline on OHLCV data.

        Args:
            symbol: Instrument symbol (e.g., "XAUUSD").
            timeframe: Timeframe string (e.g., "H1").
            ohlcv_df: OHLCV DataFrame with columns [open, high, low, close, volume].

        Returns:
            FallbackDecision with action, confidence, source tier, and levels.
        """
        # Guard: need minimum data
        if len(ohlcv_df) < 30:
            return FallbackDecision(
                action="HOLD",
                confidence=0.0,
                source_tier=FallbackTier.CONSERVATIVE,
                reasoning="Insufficient data (< 30 bars)",
            )

        # Step 1: Compute indicators
        df = compute_all_indicators(ohlcv_df)

        # Step 2: Detect patterns
        patterns_df = detect_all_patterns(ohlcv_df)

        # Step 3: Extract and aggregate signals
        ind_signals = extract_indicator_signals(df, symbol, timeframe)
        pat_signals = extract_pattern_signals(patterns_df, symbol, timeframe)
        agg = aggregate_signals(ind_signals + pat_signals, symbol=symbol)

        # Step 4: Current price and ATR
        current_price = float(df["close"].iloc[-1])
        atr_value = float(df["atr"].iloc[-1]) if "atr" in df.columns else current_price * 0.01

        # Step 4b: Detect market regime (Fase 4)
        if self.enable_regime:
            regime = self.regime_classifier.current_regime(df)
            self._current_regime = regime

            # Get regime-specific strategy and check for signal
            strategy = self.strategy_router.get_strategy(regime)
            strat_signal = strategy.on_candle(len(df) - 1, df.iloc[-1], df)
        else:
            regime = None
            strat_signal = None

        # Step 5: Map direction (prefer strategy signal over aggregated)
        direction_map = {
            SignalDirection.BULLISH: "LONG",
            SignalDirection.BEARISH: "SHORT",
            SignalDirection.NEUTRAL: "HOLD",
        }

        if strat_signal is not None:
            agg_direction = strat_signal.direction
            # Boost confidence when strategy and signals agree
            signal_dir = direction_map.get(agg.direction, "HOLD")
            if signal_dir == strat_signal.direction:
                agg_confidence = max(agg.confidence / 100.0, strat_signal.strength)
            else:
                agg_confidence = strat_signal.strength * 0.8
        else:
            agg_direction = direction_map.get(agg.direction, "HOLD")
            agg_confidence = agg.confidence / 100.0

        # Step 6: Build market state for COPER
        market_state = self._build_market_state(df, agg)
        if regime is not None:
            market_state["regime"] = float(regime)

        # Step 7: Compute z-scores for silence rule
        z_scores = self._compute_z_scores(df)

        # Step 8: Run fallback decision engine
        decision = self.fallback.decide(
            market_state=market_state,
            agg_confidence=agg_confidence,
            agg_direction=agg_direction,
            bullish_count=agg.bullish_count,
            bearish_count=agg.bearish_count,
            feature_z_scores=z_scores,
            current_price=current_price,
            atr=atr_value,
        )

        # Enrich decision with regime info
        if regime is not None:
            regime_label = REGIME_LABELS.get(regime, "UNKNOWN")
            strategy_name = self.strategy_router.get_strategy(regime).name if self.enable_regime else ""
            decision.reasoning = (
                f"[{regime_label}→{strategy_name}] {decision.reasoning}"
            )

        # Step 9: Adjust sizing by momentum
        decision.position_size_pct = self.momentum.adjust_position_size(
            decision.position_size_pct
        )

        # Step 10: Record sample for maturity tracking
        self.maturity.record_sample()

        # Step 11: Notify on actionable decisions (Fase 5)
        if decision.action in ("LONG", "SHORT") and decision.confidence >= 0.7:
            self.notifier.notify(
                NotifyLevel.TRADE_OPEN,
                f"{decision.action} {symbol} | Conf: {decision.confidence:.0%} | "
                f"{decision.reasoning}",
            )

        return decision

    def record_trade_outcome(self, trade_id: str, pnl: float,
                             is_win: bool):
        """Update stateful components after a trade closes."""
        self.momentum.record_trade(is_win)
        self.notifier.notify(
            NotifyLevel.TRADE_CLOSE,
            f"Trade {trade_id} closed | PnL: {'+'if pnl>=0 else ''}{pnl:.2f} | "
            f"{'WIN' if is_win else 'LOSS'}",
        )

    def _build_market_state(self, df: pd.DataFrame,
                            agg: AggregatedSignal) -> dict:
        """Extract a market state dict for COPER context hashing."""
        state = {}
        for col in ["rsi", "adx", "atr", "cci"]:
            if col in df.columns:
                val = df[col].iloc[-1]
                state[col] = float(val) if pd.notna(val) else 0.0

        state["bullish_count"] = float(agg.bullish_count)
        state["bearish_count"] = float(agg.bearish_count)
        state["confidence"] = float(agg.confidence)
        return state

    def _compute_z_scores(self, df: pd.DataFrame) -> dict:
        """Compute z-scores for key indicators over rolling window."""
        z_scores = {}
        for col in ["rsi", "adx", "cci"]:
            if col in df.columns and len(df) >= 50:
                series = df[col].dropna()
                if len(series) >= 50:
                    mean = float(series.iloc[-50:].mean())
                    std = max(float(series.iloc[-50:].std()), 0.01)
                    current = float(series.iloc[-1])
                    z_scores[col] = (current - mean) / std
        return z_scores
