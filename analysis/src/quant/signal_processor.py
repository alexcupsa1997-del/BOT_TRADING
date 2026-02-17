"""
Signal Processor Module

Aggregate signals from multiple sources across symbols/timeframes:
- Indicators (RSI, MACD, BB, etc.)
- Patterns (candlesticks, channels)
- Support/Resistance levels
- Generate unified signal strength
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class SignalType(Enum):
    """Signal source types."""
    INDICATOR = "indicator"
    PATTERN = "pattern"
    SUPPORT_RESISTANCE = "support_resistance"
    CHANNEL = "channel"
    MTF_CONFLUENCE = "mtf_confluence"
    SMART_MONEY = "smart_money"


class SignalDirection(Enum):
    """Signal direction."""
    BULLISH = 1
    NEUTRAL = 0
    BEARISH = -1


@dataclass
class Signal:
    """Individual signal from any source."""
    source: str           # e.g., 'RSI', 'MACD', 'DoubleBottom'
    signal_type: SignalType
    direction: SignalDirection
    strength: float       # 0-100
    timeframe: str
    symbol: str
    timestamp: pd.Timestamp
    metadata: Dict = field(default_factory=dict)


@dataclass
class AggregatedSignal:
    """Combined signal from all sources for a symbol."""
    symbol: str
    direction: SignalDirection
    confidence: float     # 0-100
    signals: List[Signal]
    bullish_count: int
    bearish_count: int
    dominant_timeframe: str
    timestamp: pd.Timestamp


# =============================================================================
# TIMEFRAME WEIGHTS
# =============================================================================

TIMEFRAME_WEIGHTS = {
    'M1': 0.05,
    'M5': 0.10,
    'M15': 0.15,
    'H1': 0.25,
    'H4': 0.25,
    'D1': 0.20,
}

SIGNAL_TYPE_WEIGHTS = {
    SignalType.INDICATOR: 0.25,
    SignalType.PATTERN: 0.20,
    SignalType.SUPPORT_RESISTANCE: 0.15,
    SignalType.CHANNEL: 0.10,
    SignalType.MTF_CONFLUENCE: 0.10,
    SignalType.SMART_MONEY: 0.20,
}


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================

def extract_indicator_signals(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str
) -> List[Signal]:
    """
    Extract signals from indicator columns in DataFrame.
    
    Expected columns: rsi, macd, macd_signal, stoch_k, stoch_d, cci, adx
    
    Returns:
        List of Signal objects
    """
    signals = []
    timestamp = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else pd.Timestamp.now()
    
    # RSI signals
    if 'rsi' in df.columns:
        rsi = df['rsi'].iloc[-1]
        if rsi < 30:
            signals.append(Signal(
                source='RSI_Oversold',
                signal_type=SignalType.INDICATOR,
                direction=SignalDirection.BULLISH,
                strength=min(100, (30 - rsi) * 3.33),
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp,
                metadata={'rsi_value': rsi}
            ))
        elif rsi > 70:
            signals.append(Signal(
                source='RSI_Overbought',
                signal_type=SignalType.INDICATOR,
                direction=SignalDirection.BEARISH,
                strength=min(100, (rsi - 70) * 3.33),
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp,
                metadata={'rsi_value': rsi}
            ))
    
    # MACD signals
    if 'macd' in df.columns and 'macd_signal' in df.columns:
        macd = df['macd'].iloc[-1]
        macd_prev = df['macd'].iloc[-2] if len(df) > 1 else macd
        signal_line = df['macd_signal'].iloc[-1]
        signal_prev = df['macd_signal'].iloc[-2] if len(df) > 1 else signal_line
        
        # Bullish crossover
        if macd_prev < signal_prev and macd > signal_line:
            signals.append(Signal(
                source='MACD_BullishCross',
                signal_type=SignalType.INDICATOR,
                direction=SignalDirection.BULLISH,
                strength=70,
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp
            ))
        # Bearish crossover
        elif macd_prev > signal_prev and macd < signal_line:
            signals.append(Signal(
                source='MACD_BearishCross',
                signal_type=SignalType.INDICATOR,
                direction=SignalDirection.BEARISH,
                strength=70,
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp
            ))
    
    # Stochastic signals
    if 'stoch_k' in df.columns and 'stoch_d' in df.columns:
        k = df['stoch_k'].iloc[-1]
        d = df['stoch_d'].iloc[-1]
        k_prev = df['stoch_k'].iloc[-2] if len(df) > 1 else k
        d_prev = df['stoch_d'].iloc[-2] if len(df) > 1 else d
        
        # Bullish crossover in oversold
        if k < 20 and k_prev < d_prev and k > d:
            signals.append(Signal(
                source='Stoch_BullishCross',
                signal_type=SignalType.INDICATOR,
                direction=SignalDirection.BULLISH,
                strength=65,
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp
            ))
        # Bearish crossover in overbought
        elif k > 80 and k_prev > d_prev and k < d:
            signals.append(Signal(
                source='Stoch_BearishCross',
                signal_type=SignalType.INDICATOR,
                direction=SignalDirection.BEARISH,
                strength=65,
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp
            ))
    
    # ADX trend strength
    if 'adx' in df.columns:
        adx = df['adx'].iloc[-1]
        if adx > 25:
            # Strong trend - direction from +DI/-DI or price
            if 'close' in df.columns:
                trend_dir = SignalDirection.BULLISH if df['close'].iloc[-1] > df['close'].iloc[-5] else SignalDirection.BEARISH
                signals.append(Signal(
                    source='ADX_StrongTrend',
                    signal_type=SignalType.INDICATOR,
                    direction=trend_dir,
                    strength=min(100, adx * 2),
                    timeframe=timeframe,
                    symbol=symbol,
                    timestamp=timestamp
                ))
    
    return signals


def extract_pattern_signals(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str
) -> List[Signal]:
    """
    Extract signals from pattern columns.
    
    Expected columns: doji, hammer, engulfing_bullish, engulfing_bearish,
                     morning_star, evening_star, double_top, double_bottom
    """
    signals = []
    timestamp = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else pd.Timestamp.now()
    
    # Candlestick patterns
    pattern_map = {
        'hammer': (SignalDirection.BULLISH, 60),
        'inverted_hammer': (SignalDirection.BULLISH, 55),
        'engulfing_bullish': (SignalDirection.BULLISH, 70),
        'engulfing_bearish': (SignalDirection.BEARISH, 70),
        'morning_star': (SignalDirection.BULLISH, 80),
        'evening_star': (SignalDirection.BEARISH, 80),
        'double_bottom': (SignalDirection.BULLISH, 85),
        'double_top': (SignalDirection.BEARISH, 85),
    }
    
    for pattern, (direction, strength) in pattern_map.items():
        if pattern in df.columns and df[pattern].iloc[-1]:
            signals.append(Signal(
                source=f'Pattern_{pattern}',
                signal_type=SignalType.PATTERN,
                direction=direction,
                strength=strength,
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp
            ))
    
    return signals


def extract_sr_signals(
    df: pd.DataFrame,
    support_levels: List[float],
    resistance_levels: List[float],
    symbol: str,
    timeframe: str
) -> List[Signal]:
    """
    Extract signals from support/resistance proximity.
    """
    signals = []
    timestamp = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else pd.Timestamp.now()
    
    if 'close' not in df.columns:
        return signals
    
    close = df['close'].iloc[-1]
    atr = df['atr'].iloc[-1] if 'atr' in df.columns else close * 0.01
    
    # Check proximity to support
    for support in support_levels:
        distance = abs(close - support) / atr
        if distance < 1.0 and close > support:
            signals.append(Signal(
                source='Support_Bounce',
                signal_type=SignalType.SUPPORT_RESISTANCE,
                direction=SignalDirection.BULLISH,
                strength=min(100, 80 * (1 - distance)),
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp,
                metadata={'level': support}
            ))
    
    # Check proximity to resistance
    for resistance in resistance_levels:
        distance = abs(close - resistance) / atr
        if distance < 1.0 and close < resistance:
            signals.append(Signal(
                source='Resistance_Rejection',
                signal_type=SignalType.SUPPORT_RESISTANCE,
                direction=SignalDirection.BEARISH,
                strength=min(100, 80 * (1 - distance)),
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp,
                metadata={'level': resistance}
            ))
    
    return signals


# =============================================================================
# SMART MONEY CONCEPT SIGNAL EXTRACTION
# =============================================================================

def extract_smc_signals(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> List[Signal]:
    """
    Extract Smart Money signals from SMC columns.

    Expected columns (added by ``detect_all_smc``):
        smc_bullish_fvg, smc_bearish_fvg, smc_fvg_distance,
        smc_bos_bullish, smc_bos_bearish, smc_choch_bullish, smc_choch_bearish,
        smc_liquidity_sweep, smc_confluence
    """
    signals: List[Signal] = []
    timestamp = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else pd.Timestamp.now()

    # FVG signals
    if "smc_bullish_fvg" in df.columns and df["smc_bullish_fvg"].iloc[-1]:
        signals.append(Signal(
            source="SMC_BullishFVG",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.BULLISH,
            strength=75,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))
    if "smc_bearish_fvg" in df.columns and df["smc_bearish_fvg"].iloc[-1]:
        signals.append(Signal(
            source="SMC_BearishFVG",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.BEARISH,
            strength=75,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))

    # BOS signals
    if "smc_bos_bullish" in df.columns and df["smc_bos_bullish"].iloc[-1]:
        signals.append(Signal(
            source="SMC_BOS_Bullish",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.BULLISH,
            strength=80,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))
    if "smc_bos_bearish" in df.columns and df["smc_bos_bearish"].iloc[-1]:
        signals.append(Signal(
            source="SMC_BOS_Bearish",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.BEARISH,
            strength=80,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))

    # CHOCH signals
    if "smc_choch_bullish" in df.columns and df["smc_choch_bullish"].iloc[-1]:
        signals.append(Signal(
            source="SMC_CHOCH_Bullish",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.BULLISH,
            strength=70,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))
    if "smc_choch_bearish" in df.columns and df["smc_choch_bearish"].iloc[-1]:
        signals.append(Signal(
            source="SMC_CHOCH_Bearish",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.BEARISH,
            strength=70,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))

    # Liquidity sweep
    if "smc_liquidity_sweep" in df.columns and df["smc_liquidity_sweep"].iloc[-1]:
        signals.append(Signal(
            source="SMC_LiquiditySweep",
            signal_type=SignalType.SMART_MONEY,
            direction=SignalDirection.NEUTRAL,
            strength=65,
            timeframe=timeframe,
            symbol=symbol,
            timestamp=timestamp,
        ))

    # Confluence score → high-confidence signal
    if "smc_confluence" in df.columns:
        conf = df["smc_confluence"].iloc[-1]
        if conf >= 60:
            # Determine direction from FVG/BOS columns
            is_bull = (
                df.get("smc_bullish_fvg", pd.Series(False)).iloc[-1]
                or df.get("smc_bos_bullish", pd.Series(False)).iloc[-1]
                or df.get("smc_choch_bullish", pd.Series(False)).iloc[-1]
            )
            is_bear = (
                df.get("smc_bearish_fvg", pd.Series(False)).iloc[-1]
                or df.get("smc_bos_bearish", pd.Series(False)).iloc[-1]
                or df.get("smc_choch_bearish", pd.Series(False)).iloc[-1]
            )
            if is_bull and not is_bear:
                direction = SignalDirection.BULLISH
            elif is_bear and not is_bull:
                direction = SignalDirection.BEARISH
            else:
                direction = SignalDirection.NEUTRAL

            signals.append(Signal(
                source="SMC_Confluence",
                signal_type=SignalType.SMART_MONEY,
                direction=direction,
                strength=min(100, conf),
                timeframe=timeframe,
                symbol=symbol,
                timestamp=timestamp,
                metadata={"confluence_score": conf},
            ))

    return signals


# =============================================================================
# SIGNAL AGGREGATION
# =============================================================================

def aggregate_signals(
    signals: List[Signal],
    symbol: str
) -> AggregatedSignal:
    """
    Aggregate multiple signals into unified signal.
    
    Uses weighted voting with timeframe and signal type weights.
    
    Args:
        signals: List of Signal objects
        symbol: Symbol name
        
    Returns:
        AggregatedSignal with confidence score
    """
    if not signals:
        return AggregatedSignal(
            symbol=symbol,
            direction=SignalDirection.NEUTRAL,
            confidence=0.0,
            signals=[],
            bullish_count=0,
            bearish_count=0,
            dominant_timeframe='',
            timestamp=pd.Timestamp.now()
        )
    
    bullish_weight = 0.0
    bearish_weight = 0.0
    bullish_count = 0
    bearish_count = 0
    tf_scores = {}
    
    for sig in signals:
        # Calculate weight
        tf_weight = TIMEFRAME_WEIGHTS.get(sig.timeframe, 0.1)
        type_weight = SIGNAL_TYPE_WEIGHTS.get(sig.signal_type, 0.1)
        strength_weight = sig.strength / 100
        
        total_weight = tf_weight * type_weight * strength_weight
        
        # Track timeframe contribution
        tf_scores[sig.timeframe] = tf_scores.get(sig.timeframe, 0) + total_weight
        
        if sig.direction == SignalDirection.BULLISH:
            bullish_weight += total_weight
            bullish_count += 1
        elif sig.direction == SignalDirection.BEARISH:
            bearish_weight += total_weight
            bearish_count += 1
    
    # Determine direction
    total_weight = bullish_weight + bearish_weight
    if total_weight == 0:
        direction = SignalDirection.NEUTRAL
        confidence = 0.0
    else:
        if bullish_weight > bearish_weight:
            direction = SignalDirection.BULLISH
            confidence = (bullish_weight / total_weight) * 100
        elif bearish_weight > bullish_weight:
            direction = SignalDirection.BEARISH
            confidence = (bearish_weight / total_weight) * 100
        else:
            direction = SignalDirection.NEUTRAL
            confidence = 50.0
    
    # Find dominant timeframe
    dominant_tf = max(tf_scores.keys(), key=lambda x: tf_scores[x]) if tf_scores else ''
    
    return AggregatedSignal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        signals=signals,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        dominant_timeframe=dominant_tf,
        timestamp=pd.Timestamp.now()
    )


# =============================================================================
# MULTI-SYMBOL PROCESSING
# =============================================================================

def process_all_symbols(
    data: Dict[str, Dict[str, pd.DataFrame]],
    sr_levels: Dict[str, Dict[str, List[float]]] = None
) -> Dict[str, AggregatedSignal]:
    """
    Process signals for all symbols across all timeframes.
    
    Args:
        data: {symbol: {timeframe: DataFrame}}
        sr_levels: {symbol: {'support': [...], 'resistance': [...]}}
        
    Returns:
        Dict of {symbol: AggregatedSignal}
    """
    results = {}
    
    for symbol, tf_data in data.items():
        all_signals = []
        
        for tf, df in tf_data.items():
            # Extract signals from each source
            all_signals.extend(extract_indicator_signals(df, symbol, tf))
            all_signals.extend(extract_pattern_signals(df, symbol, tf))
            all_signals.extend(extract_smc_signals(df, symbol, tf))

            # Add S/R signals if available
            if sr_levels and symbol in sr_levels:
                support = sr_levels[symbol].get('support', [])
                resistance = sr_levels[symbol].get('resistance', [])
                all_signals.extend(extract_sr_signals(df, support, resistance, symbol, tf))
        
        # Aggregate all signals for this symbol
        results[symbol] = aggregate_signals(all_signals, symbol)
        
        logger.info(
            f"{symbol}: {results[symbol].direction.name} "
            f"({results[symbol].confidence:.1f}% confidence, "
            f"{len(all_signals)} signals)"
        )
    
    return results


def get_top_opportunities(
    aggregated: Dict[str, AggregatedSignal],
    min_confidence: float = 60.0,
    direction: SignalDirection = None
) -> List[AggregatedSignal]:
    """
    Get top trading opportunities sorted by confidence.
    
    Args:
        aggregated: Dict of symbol -> AggregatedSignal
        min_confidence: Minimum confidence threshold
        direction: Filter by direction (optional)
        
    Returns:
        List of AggregatedSignal sorted by confidence
    """
    filtered = []
    
    for symbol, agg in aggregated.items():
        if agg.confidence < min_confidence:
            continue
        if direction and agg.direction != direction:
            continue
        if agg.direction == SignalDirection.NEUTRAL:
            continue
        
        filtered.append(agg)
    
    return sorted(filtered, key=lambda x: x.confidence, reverse=True)


# =============================================================================
# PERSISTENCE FILTER (Fase 4 — anti-whipsaw)
# =============================================================================

class PersistenceFilter:
    """
    Smooths signal direction to prevent whipsawing.

    A direction change only takes effect if the new direction persists
    for at least `min_bars` consecutive bars.
    """

    def __init__(self, min_bars: int = 3):
        self.min_bars = min_bars
        self._current_dir: SignalDirection = SignalDirection.NEUTRAL
        self._pending_dir: SignalDirection = SignalDirection.NEUTRAL
        self._count: int = 0

    def filter(self, direction: SignalDirection) -> SignalDirection:
        """Apply persistence filter to a new direction signal."""
        if direction == self._current_dir:
            self._pending_dir = direction
            self._count = 0
            return self._current_dir

        if direction == self._pending_dir:
            self._count += 1
            if self._count >= self.min_bars:
                self._current_dir = self._pending_dir
                return self._current_dir
        else:
            self._pending_dir = direction
            self._count = 1

        return self._current_dir

    def reset(self) -> None:
        """Reset filter state."""
        self._current_dir = SignalDirection.NEUTRAL
        self._pending_dir = SignalDirection.NEUTRAL
        self._count = 0
