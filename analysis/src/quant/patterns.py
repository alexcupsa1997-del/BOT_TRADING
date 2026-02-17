"""
Chart Patterns Module

Pattern recognition for GOLIATH trading system.
Supports:
- Candlestick patterns (Doji, Hammer, Engulfing, etc.)
- Chart patterns (Head & Shoulders, Double Top/Bottom, Triangles)
- Support/Resistance detection
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum


class PatternType(Enum):
    """Pattern classification."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class PatternSignal:
    """Pattern detection result."""
    name: str
    pattern_type: PatternType
    strength: float  # 0-1
    index: int


# =============================================================================
# CANDLESTICK PATTERNS
# =============================================================================

def detect_doji(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    body_ratio: float = 0.1
) -> pd.Series:
    """
    Detect Doji patterns (indecision).
    
    Args:
        open_, high, low, close: OHLC series
        body_ratio: Max body/range ratio to qualify as doji
        
    Returns:
        Boolean series where True = Doji detected
    """
    body = abs(close - open_)
    range_ = high - low
    
    # Avoid division by zero
    range_ = range_.replace(0, np.nan)
    
    return (body / range_) < body_ratio


def detect_hammer(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    shadow_ratio: float = 2.0
) -> pd.Series:
    """
    Detect Hammer patterns (bullish reversal).
    
    Args:
        open_, high, low, close: OHLC series
        shadow_ratio: Min lower shadow / body ratio
        
    Returns:
        Boolean series where True = Hammer detected
    """
    body = abs(close - open_)
    lower_shadow = np.minimum(open_, close) - low
    upper_shadow = high - np.maximum(open_, close)
    
    # Avoid division by zero
    body = body.replace(0, np.nan)
    
    is_hammer = (
        (lower_shadow / body > shadow_ratio) &
        (upper_shadow < body * 0.5) &
        (body > 0)
    )
    
    return is_hammer.fillna(False)


def detect_inverted_hammer(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    shadow_ratio: float = 2.0
) -> pd.Series:
    """
    Detect Inverted Hammer patterns.
    
    Returns:
        Boolean series where True = Inverted Hammer detected
    """
    body = abs(close - open_)
    lower_shadow = np.minimum(open_, close) - low
    upper_shadow = high - np.maximum(open_, close)
    
    body = body.replace(0, np.nan)
    
    is_inv_hammer = (
        (upper_shadow / body > shadow_ratio) &
        (lower_shadow < body * 0.5) &
        (body > 0)
    )
    
    return is_inv_hammer.fillna(False)


def detect_engulfing(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series
) -> Tuple[pd.Series, pd.Series]:
    """
    Detect Bullish and Bearish Engulfing patterns.
    
    Returns:
        Tuple of (bullish_engulfing, bearish_engulfing) boolean series
    """
    # Previous candle
    prev_open = open_.shift(1)
    prev_close = close.shift(1)
    
    # Current body engulfs previous body
    bullish = (
        (prev_close < prev_open) &  # Previous bearish
        (close > open_) &            # Current bullish
        (open_ <= prev_close) &      # Opens at or below prev close
        (close >= prev_open)         # Closes at or above prev open
    )
    
    bearish = (
        (prev_close > prev_open) &  # Previous bullish
        (close < open_) &            # Current bearish
        (open_ >= prev_close) &      # Opens at or above prev close
        (close <= prev_open)         # Closes at or below prev open
    )
    
    return bullish, bearish


def detect_morning_star(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series
) -> pd.Series:
    """
    Detect Morning Star pattern (bullish reversal, 3-candle).
    
    Returns:
        Boolean series where True = Morning Star detected
    """
    # Day 1: Long bearish
    day1_bearish = (close.shift(2) < open_.shift(2)) & \
                   (abs(close.shift(2) - open_.shift(2)) > (high.shift(2) - low.shift(2)) * 0.5)
    
    # Day 2: Small body (star)
    day2_small = abs(close.shift(1) - open_.shift(1)) < (high.shift(1) - low.shift(1)) * 0.3
    
    # Day 3: Long bullish closing above midpoint of day 1
    day1_midpoint = (open_.shift(2) + close.shift(2)) / 2
    day3_bullish = (close > open_) & (close > day1_midpoint)
    
    return day1_bearish & day2_small & day3_bullish


def detect_evening_star(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series
) -> pd.Series:
    """
    Detect Evening Star pattern (bearish reversal, 3-candle).
    
    Returns:
        Boolean series where True = Evening Star detected
    """
    # Day 1: Long bullish
    day1_bullish = (close.shift(2) > open_.shift(2)) & \
                   (abs(close.shift(2) - open_.shift(2)) > (high.shift(2) - low.shift(2)) * 0.5)
    
    # Day 2: Small body (star)
    day2_small = abs(close.shift(1) - open_.shift(1)) < (high.shift(1) - low.shift(1)) * 0.3
    
    # Day 3: Long bearish closing below midpoint of day 1
    day1_midpoint = (open_.shift(2) + close.shift(2)) / 2
    day3_bearish = (close < open_) & (close < day1_midpoint)
    
    return day1_bullish & day2_small & day3_bearish


# =============================================================================
# CHART PATTERNS
# =============================================================================

def find_local_extrema(
    series: pd.Series,
    order: int = 5
) -> Tuple[pd.Series, pd.Series]:
    """
    Find local peaks and troughs in a series.
    
    Args:
        series: Price series
        order: Number of points on each side to compare
        
    Returns:
        Tuple of (peaks, troughs) as boolean series
    """
    peaks = pd.Series(False, index=series.index)
    troughs = pd.Series(False, index=series.index)
    
    for i in range(order, len(series) - order):
        window = series.iloc[i - order:i + order + 1]
        if series.iloc[i] == window.max():
            peaks.iloc[i] = True
        if series.iloc[i] == window.min():
            troughs.iloc[i] = True
    
    return peaks, troughs


def detect_double_top(
    high: pd.Series,
    close: pd.Series,
    tolerance: float = 0.02,
    min_distance: int = 10,
    max_distance: int = 50
) -> pd.Series:
    """
    Detect Double Top pattern (bearish reversal).
    
    Args:
        high: High price series
        close: Close price series
        tolerance: Price tolerance for matching peaks
        min_distance: Minimum bars between peaks
        max_distance: Maximum bars between peaks
        
    Returns:
        Boolean series where True = Double Top detected
    """
    peaks, _ = find_local_extrema(high, order=5)
    peak_indices = peaks[peaks].index.tolist()
    
    result = pd.Series(False, index=high.index)
    
    for i, idx1 in enumerate(peak_indices):
        for idx2 in peak_indices[i + 1:]:
            pos1 = high.index.get_loc(idx1)
            pos2 = high.index.get_loc(idx2)
            distance = pos2 - pos1
            
            if min_distance <= distance <= max_distance:
                price1 = high.loc[idx1]
                price2 = high.loc[idx2]
                
                # Peaks are similar in price
                if abs(price1 - price2) / price1 < tolerance:
                    result.iloc[pos2] = True
    
    return result


def detect_double_bottom(
    low: pd.Series,
    close: pd.Series,
    tolerance: float = 0.02,
    min_distance: int = 10,
    max_distance: int = 50
) -> pd.Series:
    """
    Detect Double Bottom pattern (bullish reversal).
    """
    _, troughs = find_local_extrema(low, order=5)
    trough_indices = troughs[troughs].index.tolist()
    
    result = pd.Series(False, index=low.index)
    
    for i, idx1 in enumerate(trough_indices):
        for idx2 in trough_indices[i + 1:]:
            pos1 = low.index.get_loc(idx1)
            pos2 = low.index.get_loc(idx2)
            distance = pos2 - pos1
            
            if min_distance <= distance <= max_distance:
                price1 = low.loc[idx1]
                price2 = low.loc[idx2]
                
                if abs(price1 - price2) / price1 < tolerance:
                    result.iloc[pos2] = True
    
    return result


def detect_support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 50,
    num_levels: int = 5
) -> Tuple[List[float], List[float]]:
    """
    Detect support and resistance levels using price clustering.
    
    Args:
        high, low, close: Price series
        window: Lookback window
        num_levels: Number of levels to return
        
    Returns:
        Tuple of (support_levels, resistance_levels)
    """
    recent_high = high.tail(window)
    recent_low = low.tail(window)
    recent_close = close.tail(window)
    
    # Find peaks for resistance
    peaks, _ = find_local_extrema(recent_high, order=3)
    resistance_prices = recent_high[peaks].tolist()
    
    # Find troughs for support
    _, troughs = find_local_extrema(recent_low, order=3)
    support_prices = recent_low[troughs].tolist()
    
    # Cluster similar levels
    def cluster_levels(prices: List[float], tolerance: float = 0.01) -> List[float]:
        if not prices:
            return []
        
        prices = sorted(prices)
        clustered = []
        current_cluster = [prices[0]]
        
        for price in prices[1:]:
            if abs(price - current_cluster[-1]) / current_cluster[-1] < tolerance:
                current_cluster.append(price)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [price]
        
        clustered.append(np.mean(current_cluster))
        return clustered[-num_levels:]
    
    return cluster_levels(support_prices), cluster_levels(resistance_prices)


# =============================================================================
# PATTERN SUMMARY FUNCTION
# =============================================================================

def detect_all_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect all candlestick patterns for a given OHLCV DataFrame.
    
    Args:
        df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        
    Returns:
        DataFrame with pattern detection columns added
    """
    result = df.copy()
    
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    
    # Candlestick patterns
    result['pattern_doji'] = detect_doji(o, h, l, c)
    result['pattern_hammer'] = detect_hammer(o, h, l, c)
    result['pattern_inv_hammer'] = detect_inverted_hammer(o, h, l, c)
    
    bull_eng, bear_eng = detect_engulfing(o, h, l, c)
    result['pattern_bullish_engulfing'] = bull_eng
    result['pattern_bearish_engulfing'] = bear_eng
    
    result['pattern_morning_star'] = detect_morning_star(o, h, l, c)
    result['pattern_evening_star'] = detect_evening_star(o, h, l, c)
    
    # Chart patterns
    result['pattern_double_top'] = detect_double_top(h, c)
    result['pattern_double_bottom'] = detect_double_bottom(l, c)
    
    return result
