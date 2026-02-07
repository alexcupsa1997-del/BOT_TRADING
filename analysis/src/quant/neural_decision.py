"""
Neural Decision Manager

Generate optimal trade entry/exit signals using:
- Multi-timeframe signal confluence
- Feature vector assembly for ML models
- Entry confidence thresholds
- Position sizing recommendations
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from .signal_processor import (
    AggregatedSignal, SignalDirection, Signal,
    process_all_symbols, get_top_opportunities
)


class TradeAction(Enum):
    """Recommended trade action."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    NO_TRADE = "NO_TRADE"


@dataclass
class TradeDecision:
    """Trade decision output."""
    symbol: str
    action: TradeAction
    confidence: float          # 0-100
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_pct: float   # % of capital
    risk_reward: float
    timeframe: str
    reasoning: List[str]


@dataclass
class FeatureVector:
    """Feature vector for ML model input."""
    symbol: str
    features: np.ndarray
    feature_names: List[str]
    timestamp: pd.Timestamp


# =============================================================================
# DECISION THRESHOLDS
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    TradeAction.STRONG_BUY: 85,
    TradeAction.BUY: 70,
    TradeAction.HOLD: 50,
    TradeAction.SELL: 70,
    TradeAction.STRONG_SELL: 85,
}

# Minimum signals required from different timeframes
MIN_MTF_CONFLUENCE = 2

# Risk management
MAX_POSITION_SIZE = 0.05  # 5% of capital per trade
BASE_RISK_REWARD = 2.0    # Target 2:1 R:R


# =============================================================================
# FEATURE VECTOR ASSEMBLY
# =============================================================================

def assemble_feature_vector(
    indicator_df: pd.DataFrame,
    pattern_flags: Dict[str, bool],
    channel_info: Dict,
    sr_proximity: Dict[str, float],
    symbol: str
) -> FeatureVector:
    """
    Assemble feature vector for ML model from all signal sources.
    
    Args:
        indicator_df: DataFrame with indicator values
        pattern_flags: Dict of pattern -> bool
        channel_info: Channel detection results
        sr_proximity: Distance to support/resistance
        symbol: Symbol name
        
    Returns:
        FeatureVector ready for model input
    """
    features = []
    names = []
    
    # Indicator features (normalized to 0-100)
    indicator_cols = ['rsi', 'stoch_k', 'stoch_d', 'cci', 'adx', 'atr', 'bb_position']
    
    for col in indicator_cols:
        if col in indicator_df.columns:
            val = indicator_df[col].iloc[-1]
            features.append(normalize_value(val, col))
            names.append(f'ind_{col}')
    
    # MACD features
    if 'macd' in indicator_df.columns and 'macd_signal' in indicator_df.columns:
        macd = indicator_df['macd'].iloc[-1]
        signal = indicator_df['macd_signal'].iloc[-1]
        features.append(50 + (macd - signal) * 10)  # Centered on 50
        names.append('ind_macd_diff')
        
        # MACD momentum (histogram slope)
        if 'macd_hist' in indicator_df.columns and len(indicator_df) > 5:
            hist_slope = indicator_df['macd_hist'].iloc[-5:].diff().mean()
            features.append(50 + hist_slope * 100)
            names.append('ind_macd_momentum')
    
    # Pattern features (binary)
    pattern_list = [
        'doji', 'hammer', 'engulfing_bullish', 'engulfing_bearish',
        'morning_star', 'evening_star', 'double_top', 'double_bottom'
    ]
    
    for pattern in pattern_list:
        features.append(100 if pattern_flags.get(pattern, False) else 0)
        names.append(f'pat_{pattern}')
    
    # Channel features
    if channel_info:
        # Channel type encoding
        channel_type = channel_info.get('type', 'none')
        features.append(100 if channel_type == 'ascending' else 0)
        names.append('chan_ascending')
        features.append(100 if channel_type == 'descending' else 0)
        names.append('chan_descending')
        features.append(100 if channel_type == 'horizontal' else 0)
        names.append('chan_horizontal')
        
        # Channel position (where are we in the channel)
        features.append(channel_info.get('position', 50))
        names.append('chan_position')
    else:
        features.extend([0, 0, 0, 50])
        names.extend(['chan_ascending', 'chan_descending', 'chan_horizontal', 'chan_position'])
    
    # S/R proximity features
    features.append(sr_proximity.get('support_distance', 50))
    names.append('sr_support_dist')
    features.append(sr_proximity.get('resistance_distance', 50))
    names.append('sr_resistance_dist')
    
    return FeatureVector(
        symbol=symbol,
        features=np.array(features),
        feature_names=names,
        timestamp=pd.Timestamp.now()
    )


def normalize_value(value: float, indicator: str) -> float:
    """Normalize indicator value to 0-100 scale."""
    ranges = {
        'rsi': (0, 100),
        'stoch_k': (0, 100),
        'stoch_d': (0, 100),
        'cci': (-200, 200),
        'adx': (0, 100),
        'atr': (0, 1),  # % of price
        'bb_position': (0, 1),
    }
    
    min_val, max_val = ranges.get(indicator, (0, 100))
    clamped = max(min_val, min(max_val, value))
    return (clamped - min_val) / (max_val - min_val) * 100


# =============================================================================
# MULTI-TIMEFRAME CONFLUENCE
# =============================================================================

def check_mtf_confluence(
    signals_by_tf: Dict[str, List[Signal]],
    direction: SignalDirection
) -> Tuple[int, List[str]]:
    """
    Check how many timeframes agree on the direction.
    
    Args:
        signals_by_tf: Dict of {timeframe: [signals]}
        direction: Expected direction
        
    Returns:
        Tuple of (confluence_count, confirming_timeframes)
    """
    confirming = []
    
    for tf, signals in signals_by_tf.items():
        if not signals:
            continue
        
        # Count signals in the expected direction
        dir_count = sum(1 for s in signals if s.direction == direction)
        total = len(signals)
        
        if dir_count > total / 2:
            confirming.append(tf)
    
    return len(confirming), confirming


def get_dominant_signal(
    aggregated: AggregatedSignal
) -> Tuple[SignalDirection, float]:
    """
    Analyze signal quality and dominance.
    
    Returns:
        Tuple of (direction, quality_score)
    """
    if not aggregated.signals:
        return SignalDirection.NEUTRAL, 0.0
    
    # Separate by timeframe
    tf_signals = {}
    for sig in aggregated.signals:
        tf_signals.setdefault(sig.timeframe, []).append(sig)
    
    # Check MTF confluence
    confluence, confirming_tfs = check_mtf_confluence(
        tf_signals, aggregated.direction
    )
    
    # Quality score based on confluence and signal strength
    avg_strength = np.mean([s.strength for s in aggregated.signals])
    quality = (confluence / len(tf_signals)) * avg_strength if tf_signals else 0
    
    return aggregated.direction, quality


# =============================================================================
# DECISION GENERATION
# =============================================================================

def generate_decision(
    aggregated: AggregatedSignal,
    current_price: float,
    atr: float
) -> TradeDecision:
    """
    Generate trade decision from aggregated signal.
    
    Args:
        aggregated: Aggregated signal for symbol
        current_price: Current market price
        atr: Current ATR for stop/target calculation
        
    Returns:
        TradeDecision with entry/exit levels
    """
    direction, quality = get_dominant_signal(aggregated)
    reasoning = []
    
    # Determine action based on confidence
    confidence = aggregated.confidence
    
    if direction == SignalDirection.BULLISH:
        if confidence >= CONFIDENCE_THRESHOLDS[TradeAction.STRONG_BUY]:
            action = TradeAction.STRONG_BUY
        elif confidence >= CONFIDENCE_THRESHOLDS[TradeAction.BUY]:
            action = TradeAction.BUY
        else:
            action = TradeAction.HOLD
        
        stop_loss = current_price - (atr * 1.5)
        take_profit = current_price + (atr * 3.0)
        
    elif direction == SignalDirection.BEARISH:
        if confidence >= CONFIDENCE_THRESHOLDS[TradeAction.STRONG_SELL]:
            action = TradeAction.STRONG_SELL
        elif confidence >= CONFIDENCE_THRESHOLDS[TradeAction.SELL]:
            action = TradeAction.SELL
        else:
            action = TradeAction.HOLD
        
        stop_loss = current_price + (atr * 1.5)
        take_profit = current_price - (atr * 3.0)
        
    else:
        action = TradeAction.NO_TRADE
        stop_loss = current_price
        take_profit = current_price
    
    # Position sizing based on confidence
    if action in [TradeAction.STRONG_BUY, TradeAction.STRONG_SELL]:
        position_size = MAX_POSITION_SIZE
    elif action in [TradeAction.BUY, TradeAction.SELL]:
        position_size = MAX_POSITION_SIZE * 0.6
    else:
        position_size = 0.0
    
    # Risk/Reward calculation
    risk = abs(current_price - stop_loss)
    reward = abs(take_profit - current_price)
    rr_ratio = reward / risk if risk > 0 else 0
    
    # Build reasoning
    reasoning.append(f"Direction: {direction.name} ({confidence:.1f}% confidence)")
    reasoning.append(f"Signals: {aggregated.bullish_count} bullish, {aggregated.bearish_count} bearish")
    reasoning.append(f"Dominant TF: {aggregated.dominant_timeframe}")
    
    if aggregated.signals:
        top_signals = sorted(aggregated.signals, key=lambda x: x.strength, reverse=True)[:3]
        for sig in top_signals:
            reasoning.append(f"  - {sig.source}: {sig.strength:.0f}% ({sig.timeframe})")
    
    return TradeDecision(
        symbol=aggregated.symbol,
        action=action,
        confidence=confidence,
        entry_price=current_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size_pct=position_size,
        risk_reward=rr_ratio,
        timeframe=aggregated.dominant_timeframe,
        reasoning=reasoning
    )


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def process_decisions(
    aggregated_signals: Dict[str, AggregatedSignal],
    prices: Dict[str, float],
    atrs: Dict[str, float],
    min_confidence: float = 60.0
) -> List[TradeDecision]:
    """
    Process all symbols and generate sorted decisions.
    
    Args:
        aggregated_signals: Dict of symbol -> AggregatedSignal
        prices: Dict of symbol -> current price
        atrs: Dict of symbol -> ATR value
        min_confidence: Minimum confidence for trade
        
    Returns:
        List of TradeDecision sorted by confidence
    """
    decisions = []
    
    for symbol, agg in aggregated_signals.items():
        if agg.confidence < min_confidence:
            continue
        if agg.direction == SignalDirection.NEUTRAL:
            continue
        
        price = prices.get(symbol, 0)
        atr = atrs.get(symbol, price * 0.01)
        
        if price <= 0:
            continue
        
        decision = generate_decision(agg, price, atr)
        
        if decision.action != TradeAction.NO_TRADE:
            decisions.append(decision)
            logger.info(
                f"{symbol}: {decision.action.value} @ {price:.5f} "
                f"(SL: {decision.stop_loss:.5f}, TP: {decision.take_profit:.5f})"
            )
    
    return sorted(decisions, key=lambda x: x.confidence, reverse=True)


def get_best_entries(
    decisions: List[TradeDecision],
    max_positions: int = 3
) -> List[TradeDecision]:
    """
    Get top entry opportunities limited by max positions.
    
    Args:
        decisions: List of trade decisions
        max_positions: Maximum concurrent positions
        
    Returns:
        Top decisions limited to max_positions
    """
    # Filter only buy/sell actions
    active_entries = [
        d for d in decisions 
        if d.action in [TradeAction.STRONG_BUY, TradeAction.BUY, 
                        TradeAction.STRONG_SELL, TradeAction.SELL]
    ]
    
    return active_entries[:max_positions]
