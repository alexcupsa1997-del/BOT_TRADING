"""
Technical Indicators Module

Multi-timeframe technical indicators for GOLIATH trading system.
Supports: RSI, MACD, Bollinger Bands, ATR, Stochastic, EMA, ADX, CCI

All functions accept pandas Series/DataFrame and return indicator values.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass


@dataclass
class MACDResult:
    """MACD indicator result."""
    macd_line: pd.Series
    signal_line: pd.Series
    histogram: pd.Series


@dataclass
class BollingerResult:
    """Bollinger Bands result."""
    upper: pd.Series
    middle: pd.Series
    lower: pd.Series
    bandwidth: pd.Series


@dataclass
class StochasticResult:
    """Stochastic Oscillator result."""
    k: pd.Series
    d: pd.Series


# =============================================================================
# TREND INDICATORS
# =============================================================================

def ema(series: pd.Series, period: int = 20) -> pd.Series:
    """
    Exponential Moving Average.
    
    Args:
        series: Price series (typically close)
        period: EMA period
        
    Returns:
        EMA values
    """
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int = 20) -> pd.Series:
    """
    Simple Moving Average.
    
    Args:
        series: Price series
        period: SMA period
        
    Returns:
        SMA values
    """
    return series.rolling(window=period).mean()


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> MACDResult:
    """
    Moving Average Convergence Divergence.
    
    Args:
        close: Close price series
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)
        
    Returns:
        MACDResult with macd_line, signal_line, histogram
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return MACDResult(
        macd_line=macd_line,
        signal_line=signal_line,
        histogram=histogram
    )


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Average Directional Index - trend strength indicator.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: ADX period (default 14)
        
    Returns:
        ADX values (0-100, >25 strong trend)
    """
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    
    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)
    
    # Smoothed DM
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx_val = dx.ewm(span=period, adjust=False).mean()
    
    return adx_val


# =============================================================================
# MOMENTUM INDICATORS
# =============================================================================

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index.
    
    Args:
        close: Close price series
        period: RSI period (default 14)
        
    Returns:
        RSI values (0-100)
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi_val = 100 - (100 / (1 + rs))
    
    return rsi_val


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3
) -> StochasticResult:
    """
    Stochastic Oscillator.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        k_period: %K period (default 14)
        d_period: %D smoothing period (default 3)
        
    Returns:
        StochasticResult with %K and %D
    """
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    
    return StochasticResult(k=k, d=d)


def cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20
) -> pd.Series:
    """
    Commodity Channel Index.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: CCI period (default 20)
        
    Returns:
        CCI values (typically -100 to +100)
    """
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    
    cci_val = (tp - sma_tp) / (0.015 * mad)
    
    return cci_val


# =============================================================================
# VOLATILITY INDICATORS
# =============================================================================

def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Average True Range.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: ATR period (default 14)
        
    Returns:
        ATR values
    """
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    return tr.ewm(span=period, adjust=False).mean()


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> BollingerResult:
    """
    Bollinger Bands.
    
    Args:
        close: Close price series
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2)
        
    Returns:
        BollingerResult with upper, middle, lower, bandwidth
    """
    middle = sma(close, period)
    std = close.rolling(window=period).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    bandwidth = (upper - lower) / middle * 100
    
    return BollingerResult(
        upper=upper,
        middle=middle,
        lower=lower,
        bandwidth=bandwidth
    )


# =============================================================================
# MULTI-TIMEFRAME UTILITIES
# =============================================================================

def compute_all_indicators(
    df: pd.DataFrame,
    include_emas: List[int] = [9, 21, 50, 200]
) -> pd.DataFrame:
    """
    Compute all indicators for a given OHLCV DataFrame.
    
    Args:
        df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        include_emas: List of EMA periods to include
        
    Returns:
        DataFrame with all indicator columns added
    """
    result = df.copy()
    
    # Trend indicators
    for period in include_emas:
        result[f'ema_{period}'] = ema(df['close'], period)
    
    macd_result = macd(df['close'])
    result['macd'] = macd_result.macd_line
    result['macd_signal'] = macd_result.signal_line
    result['macd_hist'] = macd_result.histogram
    
    result['adx'] = adx(df['high'], df['low'], df['close'])
    
    # Momentum indicators
    result['rsi'] = rsi(df['close'])
    
    stoch_result = stochastic(df['high'], df['low'], df['close'])
    result['stoch_k'] = stoch_result.k
    result['stoch_d'] = stoch_result.d
    
    result['cci'] = cci(df['high'], df['low'], df['close'])
    
    # Volatility indicators
    result['atr'] = atr(df['high'], df['low'], df['close'])
    
    bb_result = bollinger_bands(df['close'])
    result['bb_upper'] = bb_result.upper
    result['bb_middle'] = bb_result.middle
    result['bb_lower'] = bb_result.lower
    result['bb_bandwidth'] = bb_result.bandwidth
    
    return result


def resample_ohlcv(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resample OHLCV data to a higher timeframe.
    
    Args:
        df: DataFrame with DatetimeIndex and OHLCV columns
        timeframe: Target timeframe ('5T', '15T', '1H', '4H', '1D')
        
    Returns:
        Resampled DataFrame
    """
    resampled = df.resample(timeframe).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    return resampled
