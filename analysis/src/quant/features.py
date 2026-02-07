"""
Feature Engineering Module

Advanced feature engineering for ML-based trading:
- Fractional Differencing (memory-preserving stationarity)
- Triple Barrier Labeling (trade classification)
- Feature aggregation utilities
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, List
from dataclasses import dataclass
from loguru import logger


@dataclass
class TripleBarrierResult:
    """Result from triple barrier labeling."""
    labels: pd.Series      # -1 (SL), 0 (timeout), 1 (TP)
    barriers: pd.DataFrame  # first_touch, barrier_type, return


# =============================================================================
# FRACTIONAL DIFFERENCING
# =============================================================================

def get_weights_ffd(d: float, threshold: float = 1e-5) -> np.ndarray:
    """
    Calculate weights for FFD (Fixed-width window Fractional Differentiation).
    
    The weight for lag k is: w_k = -w_{k-1} * (d - k + 1) / k
    
    Args:
        d: Differencing order (0 < d < 1 for fractional)
        threshold: Minimum weight magnitude to include
        
    Returns:
        Array of weights
    """
    weights = [1.0]
    k = 1
    
    while True:
        w = -weights[-1] * (d - k + 1) / k
        if abs(w) < threshold:
            break
        weights.append(w)
        k += 1
    
    return np.array(weights[::-1]).reshape(-1, 1)


def fractional_differencing(
    series: pd.Series,
    d: float = 0.4,
    threshold: float = 1e-5
) -> pd.Series:
    """
    Apply fractional differencing to make series stationary while preserving memory.
    
    Standard differencing (d=1) removes all memory.
    Fractional differencing (0 < d < 1) preserves some memory.
    
    Typical values:
    - d=0.3-0.5 for most financial series
    - Use ADF test to find minimum d for stationarity
    
    Args:
        series: Price series (pandas Series with DatetimeIndex)
        d: Differencing order (default 0.4)
        threshold: Weight cutoff threshold
        
    Returns:
        Fractionally differenced series
    """
    weights = get_weights_ffd(d, threshold)
    width = len(weights)
    
    # Prepare output
    result = pd.Series(index=series.index, dtype=float)
    
    # Apply convolution
    for i in range(width - 1, len(series)):
        window = series.iloc[i - width + 1:i + 1].values
        result.iloc[i] = np.dot(weights.T, window)[0]
    
    return result


def find_optimal_d(
    series: pd.Series,
    d_range: Tuple[float, float] = (0.0, 1.0),
    num_steps: int = 11,
    significance: float = 0.05
) -> float:
    """
    Find minimum d that makes series stationary (ADF test).
    
    Args:
        series: Price series
        d_range: Range of d values to test
        num_steps: Number of d values to test
        significance: ADF significance level
        
    Returns:
        Optimal d value
    """
    from statsmodels.tsa.stattools import adfuller
    
    d_values = np.linspace(d_range[0], d_range[1], num_steps)
    
    for d in d_values:
        if d == 0:
            diff_series = series
        else:
            diff_series = fractional_differencing(series, d)
        
        diff_series = diff_series.dropna()
        if len(diff_series) < 20:
            continue
            
        try:
            adf_stat, p_value, *_ = adfuller(diff_series)
            if p_value < significance:
                logger.info(f"Found optimal d={d:.2f} (p-value={p_value:.4f})")
                return d
        except Exception:
            continue
    
    logger.warning("Could not find stationary d, using d=1.0")
    return 1.0


# =============================================================================
# TRIPLE BARRIER LABELING
# =============================================================================

def triple_barrier_labels(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    tp_pct: float = 0.02,
    sl_pct: float = 0.01,
    max_holding_periods: int = 60,
    side: int = 1  # 1 for long, -1 for short
) -> TripleBarrierResult:
    """
    Apply Triple Barrier Method for trade labeling.
    
    Three barriers define trade outcome:
    1. Upper barrier (Take Profit): Price reaches +tp_pct
    2. Lower barrier (Stop Loss): Price reaches -sl_pct
    3. Vertical barrier (Time): Maximum holding period reached
    
    Labels:
    - 1: TP hit first (profitable trade)
    - -1: SL hit first (losing trade)
    - 0: Timeout (exit flat)
    
    Args:
        close: Close price series
        high: High price series (for intrabar touches)
        low: Low price series
        tp_pct: Take profit percentage (default 2%)
        sl_pct: Stop loss percentage (default 1%)
        max_holding_periods: Maximum bars to hold
        side: Trade direction (1=long, -1=short)
        
    Returns:
        TripleBarrierResult with labels and barrier info
    """
    labels = pd.Series(index=close.index, dtype=float)
    barriers = pd.DataFrame(
        index=close.index,
        columns=['first_touch', 'barrier_type', 'return']
    )
    
    for i in range(len(close) - max_holding_periods):
        entry_price = close.iloc[i]
        entry_idx = close.index[i]
        
        # Calculate barrier levels
        if side == 1:  # Long
            tp_level = entry_price * (1 + tp_pct)
            sl_level = entry_price * (1 - sl_pct)
        else:  # Short
            tp_level = entry_price * (1 - tp_pct)
            sl_level = entry_price * (1 + sl_pct)
        
        # Look forward
        first_touch_bar = None
        barrier_type = None
        
        for j in range(1, max_holding_periods + 1):
            bar_idx = i + j
            if bar_idx >= len(close):
                break
            
            bar_high = high.iloc[bar_idx]
            bar_low = low.iloc[bar_idx]
            
            if side == 1:  # Long
                # Check TP (high touches upper barrier)
                if bar_high >= tp_level:
                    first_touch_bar = j
                    barrier_type = 'TP'
                    break
                # Check SL (low touches lower barrier)
                if bar_low <= sl_level:
                    first_touch_bar = j
                    barrier_type = 'SL'
                    break
            else:  # Short
                # Check TP (low touches lower barrier)
                if bar_low <= tp_level:
                    first_touch_bar = j
                    barrier_type = 'TP'
                    break
                # Check SL (high touches upper barrier)
                if bar_high >= sl_level:
                    first_touch_bar = j
                    barrier_type = 'SL'
                    break
        
        # Assign label
        if barrier_type == 'TP':
            labels.iloc[i] = 1
        elif barrier_type == 'SL':
            labels.iloc[i] = -1
        else:
            labels.iloc[i] = 0
            first_touch_bar = max_holding_periods
            barrier_type = 'TIME'
        
        # Record barrier info
        exit_idx = i + first_touch_bar
        if exit_idx < len(close):
            exit_price = close.iloc[exit_idx]
            ret = (exit_price - entry_price) / entry_price * side
            barriers.loc[entry_idx] = [first_touch_bar, barrier_type, ret]
    
    return TripleBarrierResult(labels=labels, barriers=barriers)


def compute_meta_labels(
    primary_labels: pd.Series,
    secondary_model_probs: pd.Series,
    threshold: float = 0.5
) -> pd.Series:
    """
    Compute meta-labels for secondary model (bet sizing).
    
    Meta-labeling approach:
    1. Primary model predicts direction (side)
    2. Secondary model predicts probability of success
    3. Bet size = probability * primary direction
    
    Args:
        primary_labels: Labels from primary model (-1, 0, 1)
        secondary_model_probs: Probability of success from secondary model
        threshold: Probability threshold for taking trade
        
    Returns:
        Meta-labels (0 = no trade, 1 = take trade)
    """
    meta_labels = pd.Series(0, index=primary_labels.index)
    
    # Only label trades where primary model has direction
    active_trades = primary_labels != 0
    
    # Meta-label = 1 if probability exceeds threshold
    meta_labels[active_trades] = (secondary_model_probs[active_trades] > threshold).astype(int)
    
    return meta_labels


# =============================================================================
# ROLLING STATISTICS
# =============================================================================

def compute_rolling_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: bool = True,
    periods_per_year: int = 252
) -> pd.Series:
    """
    Compute rolling volatility.
    
    Args:
        returns: Return series
        window: Rolling window size
        annualize: Whether to annualize
        periods_per_year: Trading periods per year
        
    Returns:
        Rolling volatility series
    """
    vol = returns.rolling(window=window).std()
    
    if annualize:
        vol = vol * np.sqrt(periods_per_year)
    
    return vol


def compute_rolling_sharpe(
    returns: pd.Series,
    window: int = 60,
    risk_free: float = 0.0,
    periods_per_year: int = 252
) -> pd.Series:
    """
    Compute rolling Sharpe ratio.
    
    Args:
        returns: Return series
        window: Rolling window size
        risk_free: Risk-free rate (annualized)
        periods_per_year: Trading periods per year
        
    Returns:
        Rolling Sharpe ratio
    """
    excess_returns = returns - (risk_free / periods_per_year)
    mean_ret = excess_returns.rolling(window=window).mean()
    vol = excess_returns.rolling(window=window).std()
    
    sharpe = (mean_ret / vol) * np.sqrt(periods_per_year)
    
    return sharpe
