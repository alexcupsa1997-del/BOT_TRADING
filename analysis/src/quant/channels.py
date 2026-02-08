"""
Channel Detection Module

Detect price channels across multiple timeframes:
- Ascending channels (bullish)
- Descending channels (bearish)
- Horizontal channels (consolidation)
- Breakout detection
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, List, Dict
from dataclasses import dataclass
from scipy import stats
from loguru import logger


@dataclass
class Channel:
    """Detected channel with properties."""
    channel_type: str  # 'ascending', 'descending', 'horizontal'
    upper_slope: float
    lower_slope: float
    upper_intercept: float
    lower_intercept: float
    start_idx: int
    end_idx: int
    width: float
    r_squared: float  # Quality of fit
    timeframe: str


@dataclass
class ChannelBreakout:
    """Channel breakout event."""
    direction: str  # 'up' or 'down'
    idx: int
    price: float
    channel: Channel
    strength: float  # 0-1


# =============================================================================
# CHANNEL DETECTION
# =============================================================================

def detect_channel(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    lookback: int = 50,
    min_touches: int = 3,
    tolerance: float = 0.02
) -> Optional[Channel]:
    """
    Detect price channel using linear regression on swing points.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        lookback: Number of bars to analyze
        min_touches: Minimum touches on channel lines
        tolerance: Price tolerance for touches (2%)
        
    Returns:
        Channel object if detected, None otherwise
    """
    if len(high) < lookback:
        return None
    
    # Use recent data
    h = high.iloc[-lookback:].values
    l = low.iloc[-lookback:].values
    c = close.iloc[-lookback:].values
    x = np.arange(lookback)
    
    # Find swing highs and lows
    swing_highs = find_swing_points(h, order=5, is_high=True)
    swing_lows = find_swing_points(l, order=5, is_high=False)
    
    if len(swing_highs) < min_touches or len(swing_lows) < min_touches:
        return None
    
    # Linear regression on swing points
    upper_slope, upper_intercept, upper_r, _, _ = stats.linregress(
        swing_highs[:, 0], swing_highs[:, 1]
    )
    lower_slope, lower_intercept, lower_r, _, _ = stats.linregress(
        swing_lows[:, 0], swing_lows[:, 1]
    )
    
    # Determine channel type
    avg_slope = (upper_slope + lower_slope) / 2
    if avg_slope > tolerance / lookback:
        channel_type = 'ascending'
    elif avg_slope < -tolerance / lookback:
        channel_type = 'descending'
    else:
        channel_type = 'horizontal'
    
    # Calculate channel width (average distance between lines)
    upper_line = upper_slope * x + upper_intercept
    lower_line = lower_slope * x + lower_intercept
    width = np.mean(upper_line - lower_line)
    
    # R-squared quality
    r_squared = (upper_r ** 2 + lower_r ** 2) / 2
    
    return Channel(
        channel_type=channel_type,
        upper_slope=upper_slope,
        lower_slope=lower_slope,
        upper_intercept=upper_intercept,
        lower_intercept=lower_intercept,
        start_idx=len(high) - lookback,
        end_idx=len(high) - 1,
        width=width,
        r_squared=r_squared,
        timeframe=''  # Set by caller
    )


def find_swing_points(
    prices: np.ndarray,
    order: int = 5,
    is_high: bool = True
) -> np.ndarray:
    """
    Find swing highs or lows.
    
    Args:
        prices: Price array
        order: Number of bars on each side
        is_high: True for swing highs, False for lows
        
    Returns:
        Array of [index, price] for each swing point
    """
    swings = []
    
    for i in range(order, len(prices) - order):
        if is_high:
            if all(prices[i] >= prices[i-order:i]) and all(prices[i] >= prices[i+1:i+order+1]):
                swings.append([i, prices[i]])
        else:
            if all(prices[i] <= prices[i-order:i]) and all(prices[i] <= prices[i+1:i+order+1]):
                swings.append([i, prices[i]])
    
    return np.array(swings) if swings else np.array([]).reshape(0, 2)


def detect_breakout(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    channel: Channel
) -> Optional[ChannelBreakout]:
    """
    Detect if price has broken out of channel.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        channel: Detected channel
        
    Returns:
        ChannelBreakout if detected, None otherwise
    """
    if channel is None:
        return None
    
    # Get last bar
    last_idx = len(close) - 1
    last_high = high.iloc[-1]
    last_low = low.iloc[-1]
    last_close = close.iloc[-1]
    
    # Calculate channel lines at current bar
    x = last_idx - channel.start_idx
    upper_level = channel.upper_slope * x + channel.upper_intercept
    lower_level = channel.lower_slope * x + channel.lower_intercept
    
    # Check for breakout
    if last_close > upper_level:
        strength = min(1.0, (last_close - upper_level) / (channel.width * 0.5))
        return ChannelBreakout(
            direction='up',
            idx=last_idx,
            price=last_close,
            channel=channel,
            strength=strength
        )
    elif last_close < lower_level:
        strength = min(1.0, (lower_level - last_close) / (channel.width * 0.5))
        return ChannelBreakout(
            direction='down',
            idx=last_idx,
            price=last_close,
            channel=channel,
            strength=strength
        )
    
    return None


# =============================================================================
# MULTI-TIMEFRAME CHANNELS
# =============================================================================

def detect_channels_mtf(
    ohlcv_dict: Dict[str, pd.DataFrame],
    timeframes: List[str] = None
) -> Dict[str, Channel]:
    """
    Detect channels across multiple timeframes.
    
    Args:
        ohlcv_dict: Dict of {timeframe: OHLCV DataFrame}
        timeframes: List of timeframes to analyze
        
    Returns:
        Dict of {timeframe: Channel}
    """
    if timeframes is None:
        timeframes = ['M5', 'M15', 'H1', 'H4', 'D1']
    
    channels = {}
    
    for tf in timeframes:
        if tf not in ohlcv_dict:
            continue
            
        df = ohlcv_dict[tf]
        if len(df) < 50:
            continue
        
        channel = detect_channel(df['high'], df['low'], df['close'])
        
        if channel is not None:
            channel.timeframe = tf
            channels[tf] = channel
            logger.debug(f"{tf}: {channel.channel_type} channel (R²={channel.r_squared:.2f})")
    
    return channels


def get_channel_confluence(
    channels: Dict[str, Channel]
) -> Dict[str, float]:
    """
    Calculate channel confluence across timeframes.
    
    Higher timeframe channels carry more weight.
    
    Args:
        channels: Dict of {timeframe: Channel}
        
    Returns:
        Dict with bullish/bearish/neutral scores
    """
    # Timeframe weights (higher = more important)
    weights = {
        'M1': 0.05, 'M5': 0.10, 'M15': 0.15,
        'H1': 0.25, 'H4': 0.20, 'D1': 0.25
    }
    
    bullish_score = 0.0
    bearish_score = 0.0
    total_weight = 0.0
    
    for tf, channel in channels.items():
        weight = weights.get(tf, 0.1) * channel.r_squared
        total_weight += weight
        
        if channel.channel_type == 'ascending':
            bullish_score += weight
        elif channel.channel_type == 'descending':
            bearish_score += weight
    
    if total_weight == 0:
        return {'bullish': 0, 'bearish': 0, 'neutral': 1.0}
    
    return {
        'bullish': bullish_score / total_weight,
        'bearish': bearish_score / total_weight,
        'neutral': 1 - (bullish_score + bearish_score) / total_weight
    }


# =============================================================================
# WEDGE & TRIANGLE PATTERNS
# =============================================================================

def detect_wedge(
    high: pd.Series,
    low: pd.Series,
    lookback: int = 50
) -> Optional[Dict]:
    """
    Detect wedge patterns (converging channel lines).
    
    Rising wedge (bearish): Both lines ascending, converging
    Falling wedge (bullish): Both lines descending, converging
    
    Returns:
        Dict with pattern info or None
    """
    channel = detect_channel(high, low, high, lookback)
    if channel is None:
        return None
    
    # Check if lines are converging
    slope_diff = abs(channel.upper_slope - channel.lower_slope)
    if slope_diff < 0.0001:  # Not converging enough
        return None
    
    # Check direction
    if channel.upper_slope > 0 and channel.lower_slope > 0:
        return {
            'pattern': 'rising_wedge',
            'bias': 'bearish',
            'strength': channel.r_squared
        }
    elif channel.upper_slope < 0 and channel.lower_slope < 0:
        return {
            'pattern': 'falling_wedge',
            'bias': 'bullish',
            'strength': channel.r_squared
        }
    
    return None


def detect_triangle(
    high: pd.Series,
    low: pd.Series,
    lookback: int = 50,
    slope_threshold: float = 0.0005
) -> Optional[Dict]:
    """
    Detect triangle patterns.
    
    Ascending triangle (bullish): Flat top, rising bottom
    Descending triangle (bearish): Flat bottom, falling top
    Symmetrical triangle (neutral): Converging sloped lines
    
    Returns:
        Dict with pattern info or None
    """
    channel = detect_channel(high, low, high, lookback)
    if channel is None:
        return None
    
    upper_flat = abs(channel.upper_slope) < slope_threshold
    lower_flat = abs(channel.lower_slope) < slope_threshold
    
    if upper_flat and channel.lower_slope > 0:
        return {
            'pattern': 'ascending_triangle',
            'bias': 'bullish',
            'strength': channel.r_squared
        }
    elif lower_flat and channel.upper_slope < 0:
        return {
            'pattern': 'descending_triangle',
            'bias': 'bearish',
            'strength': channel.r_squared
        }
    elif not upper_flat and not lower_flat:
        # Check if converging
        if (channel.upper_slope < 0 and channel.lower_slope > 0):
            return {
                'pattern': 'symmetrical_triangle',
                'bias': 'neutral',
                'strength': channel.r_squared
            }
    
    return None
