"""
Indicator Optimizer Module

Auto-tune indicator parameters for each symbol/timeframe:
- Find optimal RSI period
- Optimize MACD fast/slow/signal
- Tune Bollinger Band parameters
- Per-symbol parameter persistence
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class OptimizedParams:
    """Optimized indicator parameters for a symbol."""
    symbol: str
    timeframe: str
    rsi_period: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    bb_period: int
    bb_std: float
    atr_period: int
    stoch_k: int
    stoch_d: int
    score: float  # Optimization score


# =============================================================================
# DEFAULT PARAMETER RANGES
# =============================================================================

PARAM_RANGES = {
    'rsi_period': [7, 9, 14, 21],
    'macd_fast': [8, 10, 12, 15],
    'macd_slow': [21, 24, 26, 30],
    'macd_signal': [7, 9, 12],
    'bb_period': [15, 20, 25],
    'bb_std': [1.5, 2.0, 2.5],
    'atr_period': [10, 14, 20],
    'stoch_k': [9, 14, 21],
    'stoch_d': [3, 5],
}

# Timeframe-specific adjustments
TIMEFRAME_MULTIPLIERS = {
    'M1': {'period_mult': 0.7, 'volatility_adj': 1.3},
    'M5': {'period_mult': 0.8, 'volatility_adj': 1.2},
    'M15': {'period_mult': 0.9, 'volatility_adj': 1.1},
    'H1': {'period_mult': 1.0, 'volatility_adj': 1.0},
    'H4': {'period_mult': 1.1, 'volatility_adj': 0.9},
    'D1': {'period_mult': 1.2, 'volatility_adj': 0.8},
}


# =============================================================================
# OPTIMIZATION FUNCTIONS
# =============================================================================

def optimize_rsi(
    close: pd.Series,
    labels: pd.Series,
    periods: List[int] = None
) -> Tuple[int, float]:
    """
    Find optimal RSI period by maximizing prediction accuracy.
    
    Args:
        close: Close price series
        labels: Triple barrier labels (-1, 0, 1)
        periods: List of periods to test
        
    Returns:
        Tuple of (best_period, score)
    """
    if periods is None:
        periods = PARAM_RANGES['rsi_period']
    
    best_period = 14
    best_score = 0.0
    
    for period in periods:
        rsi = compute_rsi(close, period)
        
        # Score based on oversold->up and overbought->down correlation
        oversold_signal = (rsi < 30).astype(int)
        overbought_signal = (rsi > 70).astype(int)
        
        # Align with labels
        aligned = pd.DataFrame({
            'oversold': oversold_signal,
            'overbought': overbought_signal,
            'label': labels
        }).dropna()
        
        if len(aligned) < 50:
            continue
        
        # Score: oversold predicts up, overbought predicts down
        up_accuracy = (aligned[aligned['oversold'] == 1]['label'] == 1).mean()
        down_accuracy = (aligned[aligned['overbought'] == 1]['label'] == -1).mean()
        
        score = (up_accuracy + down_accuracy) / 2 if not np.isnan(up_accuracy) else 0
        
        if score > best_score:
            best_score = score
            best_period = period
    
    return best_period, best_score


def optimize_macd(
    close: pd.Series,
    labels: pd.Series
) -> Tuple[Dict[str, int], float]:
    """
    Find optimal MACD parameters.
    
    Args:
        close: Close price series
        labels: Triple barrier labels
        
    Returns:
        Tuple of (params_dict, score)
    """
    best_params = {'fast': 12, 'slow': 26, 'signal': 9}
    best_score = 0.0
    
    for fast in PARAM_RANGES['macd_fast']:
        for slow in PARAM_RANGES['macd_slow']:
            if fast >= slow:
                continue
            for signal in PARAM_RANGES['macd_signal']:
                macd_line, signal_line, hist = compute_macd(close, fast, slow, signal)
                
                # Score based on histogram direction predicting labels
                hist_signal = np.sign(hist)
                
                aligned = pd.DataFrame({
                    'hist': hist_signal,
                    'label': labels
                }).dropna()
                
                if len(aligned) < 50:
                    continue
                
                accuracy = (aligned['hist'] == aligned['label']).mean()
                
                if accuracy > best_score:
                    best_score = accuracy
                    best_params = {'fast': fast, 'slow': slow, 'signal': signal}
    
    return best_params, best_score


def optimize_bollinger(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series
) -> Tuple[Dict, float]:
    """
    Find optimal Bollinger Band parameters.
    
    Optimizes for mean reversion signals.
    
    Returns:
        Tuple of (params_dict, score)
    """
    best_params = {'period': 20, 'std': 2.0}
    best_score = 0.0
    
    for period in PARAM_RANGES['bb_period']:
        for std in PARAM_RANGES['bb_std']:
            upper, middle, lower = compute_bollinger(close, period, std)
            
            # Score: touches on bands followed by reversal
            touch_upper = (high >= upper).astype(int)
            touch_lower = (low <= lower).astype(int)
            
            # Look at next bar return
            returns = close.pct_change().shift(-1)
            
            # Upper touch should lead to negative return
            upper_score = -(returns[touch_upper == 1]).mean() if touch_upper.sum() > 0 else 0
            # Lower touch should lead to positive return
            lower_score = (returns[touch_lower == 1]).mean() if touch_lower.sum() > 0 else 0
            
            score = (upper_score + lower_score) / 2 if not np.isnan(upper_score) else 0
            
            if score > best_score:
                best_score = score
                best_params = {'period': period, 'std': std}
    
    return best_params, best_score


# =============================================================================
# MULTI-TIMEFRAME OPTIMIZATION
# =============================================================================

def optimize_for_symbol(
    ohlcv_dict: Dict[str, pd.DataFrame],
    labels_dict: Dict[str, pd.Series],
    symbol: str
) -> Dict[str, OptimizedParams]:
    """
    Optimize indicators for a symbol across all timeframes.
    
    Args:
        ohlcv_dict: Dict of {timeframe: OHLCV DataFrame}
        labels_dict: Dict of {timeframe: labels Series}
        symbol: Symbol name
        
    Returns:
        Dict of {timeframe: OptimizedParams}
    """
    results = {}
    
    for tf, df in ohlcv_dict.items():
        if tf not in labels_dict or len(df) < 100:
            continue
        
        labels = labels_dict[tf]
        close = df['close']
        high = df['high']
        low = df['low']
        
        logger.info(f"Optimizing {symbol} {tf}...")
        
        # Optimize each indicator
        rsi_period, rsi_score = optimize_rsi(close, labels)
        macd_params, macd_score = optimize_macd(close, labels)
        bb_params, bb_score = optimize_bollinger(close, high, low)
        
        # Apply timeframe adjustments
        tf_adj = TIMEFRAME_MULTIPLIERS.get(tf, {'period_mult': 1.0})
        
        results[tf] = OptimizedParams(
            symbol=symbol,
            timeframe=tf,
            rsi_period=rsi_period,
            macd_fast=macd_params['fast'],
            macd_slow=macd_params['slow'],
            macd_signal=macd_params['signal'],
            bb_period=bb_params['period'],
            bb_std=bb_params['std'],
            atr_period=int(14 * tf_adj['period_mult']),
            stoch_k=14,
            stoch_d=3,
            score=(rsi_score + macd_score + bb_score) / 3
        )
        
        logger.info(f"  {tf}: RSI={rsi_period}, MACD={macd_params}, Score={results[tf].score:.3f}")
    
    return results


# =============================================================================
# HELPER INDICATOR FUNCTIONS
# =============================================================================

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD line, signal line, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(
    close: pd.Series,
    period: int = 20,
    std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger Bands."""
    middle = close.rolling(period).mean()
    std_dev = close.rolling(period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    return upper, middle, lower


# =============================================================================
# SCALE NORMALIZATION
# =============================================================================

def normalize_indicator_scale(
    value: float,
    indicator: str
) -> float:
    """
    Normalize indicator value to 0-100 scale.
    
    Args:
        value: Raw indicator value
        indicator: Indicator name
        
    Returns:
        Normalized value 0-100
    """
    scales = {
        'rsi': (0, 100),           # Already 0-100
        'stoch_k': (0, 100),       # Already 0-100
        'stoch_d': (0, 100),       # Already 0-100
        'cci': (-200, 200),        # Typical range
        'adx': (0, 100),           # Already 0-100
        'macd_hist': (-1, 1),      # Normalized by ATR
        'bb_position': (0, 1),     # Within bands
    }
    
    if indicator not in scales:
        return value
    
    min_val, max_val = scales[indicator]
    
    # Clamp and normalize
    clamped = max(min_val, min(max_val, value))
    normalized = (clamped - min_val) / (max_val - min_val) * 100
    
    return normalized
