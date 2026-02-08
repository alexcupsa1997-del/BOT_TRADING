"""
Signal Generation Module

Implements advanced feature engineering for trading signals:
- Fractional Differencing for stationary time-series
- Triple Barrier Method for trade labeling
- Technical indicators (SMA, EMA, RSI, Bollinger)
- Feature Orthogonalization with PCA
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class BarrierLabel(Enum):
    """Labels for Triple Barrier Method."""
    TAKE_PROFIT = 1
    STOP_LOSS = -1
    TIMEOUT = 0


@dataclass
class TripleBarrierConfig:
    """Configuration for Triple Barrier labeling."""
    take_profit_pct: float = 0.02  # 2% take profit
    stop_loss_pct: float = 0.01    # 1% stop loss
    max_holding_period: int = 100  # bars


def fractional_differencing(
    series: np.ndarray,
    d: float = 0.5,
    threshold: float = 1e-5,
) -> np.ndarray:
    """
    Apply fractional differencing to make series stationary while preserving memory.
    
    This is superior to integer differencing (d=1) because it:
    - Preserves more information about the original series
    - Maintains stationarity while keeping predictive signal
    
    Args:
        series: Input price series
        d: Differencing order (0 < d < 1 for fractional)
        threshold: Weight cutoff for computational efficiency
        
    Returns:
        Fractionally differenced series
    """
    # Calculate weights using binomial expansion
    def get_weights(d: float, size: int, threshold: float) -> np.ndarray:
        weights = [1.0]
        for k in range(1, size):
            w = -weights[-1] * (d - k + 1) / k
            if abs(w) < threshold:
                break
            weights.append(w)
        return np.array(weights[::-1])
    
    weights = get_weights(d, len(series), threshold)
    width = len(weights)
    
    # Apply convolution
    result = np.full(len(series), np.nan)
    for i in range(width - 1, len(series)):
        result[i] = np.dot(weights, series[i - width + 1:i + 1])
    
    return result


def find_optimal_d(
    series: np.ndarray,
    d_range: Tuple[float, float] = (0.0, 1.0),
    steps: int = 20,
    adf_threshold: float = -2.86,  # 5% significance level
) -> float:
    """
    Find minimum d that achieves stationarity.
    
    Uses ADF test to check stationarity at each d value.
    Returns the smallest d that passes the stationarity test.
    """
    
    for d in np.linspace(d_range[0], d_range[1], steps):
        if d == 0:
            continue
            
        diffed = fractional_differencing(series, d)
        clean = diffed[~np.isnan(diffed)]
        
        if len(clean) < 20:
            continue
            
        # Simple ADF-like test (simplified)
        # In production, use statsmodels.tsa.stattools.adfuller
        try:
            diff1 = np.diff(clean)
            if np.std(diff1) > 0:
                t_stat = np.mean(diff1) / (np.std(diff1) / np.sqrt(len(diff1)))
                if t_stat < adf_threshold:
                    logger.info(f"Found optimal d={d:.3f} for stationarity")
                    return d
        except Exception:
            continue
    
    return 1.0  # Fall back to full differencing


def triple_barrier_labels(
    prices: np.ndarray,
    config: TripleBarrierConfig,
) -> np.ndarray:
    """
    Implement Triple Barrier Method for trade labeling.
    
    Creates labels based on which barrier is touched first:
    - Upper barrier (take profit): label = 1
    - Lower barrier (stop loss): label = -1
    - Time barrier (timeout): label = 0
    
    This is superior to fixed-horizon returns because:
    - Accounts for path dependency
    - More realistic trading targets
    - Reduces noise in labels
    """
    n = len(prices)
    labels = np.zeros(n)
    
    for i in range(n - config.max_holding_period):
        entry_price = prices[i]
        upper_barrier = entry_price * (1 + config.take_profit_pct)
        lower_barrier = entry_price * (1 - config.stop_loss_pct)
        
        # Check which barrier is touched first
        for j in range(1, config.max_holding_period + 1):
            if i + j >= n:
                break
                
            current_price = prices[i + j]
            
            if current_price >= upper_barrier:
                labels[i] = BarrierLabel.TAKE_PROFIT.value
                break
            elif current_price <= lower_barrier:
                labels[i] = BarrierLabel.STOP_LOSS.value
                break
            elif j == config.max_holding_period:
                # Timeout - use final return direction
                final_return = (current_price - entry_price) / entry_price
                labels[i] = np.sign(final_return)
    
    return labels


class TechnicalIndicators:
    """Technical indicator calculations using vectorized operations."""
    
    @staticmethod
    def sma(prices: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        if len(prices) < period:
            return np.full(len(prices), np.nan)
        
        weights = np.ones(period) / period
        sma = np.convolve(prices, weights, mode='valid')
        return np.concatenate([np.full(period - 1, np.nan), sma])
    
    @staticmethod
    def ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        alpha = 2 / (period + 1)
        ema = np.zeros(len(prices))
        ema[0] = prices[0]
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
        
        return ema
    
    @staticmethod
    def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros(len(prices))
        avg_loss = np.zeros(len(prices))
        
        # Initial average
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
        
        # Smoothed moving average
        for i in range(period + 1, len(prices)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period
        
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
        rsi = 100 - (100 / (1 + rs))
        
        rsi[:period] = np.nan
        return rsi
    
    @staticmethod
    def bollinger_bands(
        prices: np.ndarray,
        period: int = 20,
        num_std: float = 2.0,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands: middle, upper, lower."""
        middle = TechnicalIndicators.sma(prices, period)
        
        # Rolling standard deviation
        std = np.zeros(len(prices))
        for i in range(period - 1, len(prices)):
            std[i] = np.std(prices[i - period + 1:i + 1])
        std[:period - 1] = np.nan
        
        upper = middle + num_std * std
        lower = middle - num_std * std
        
        return middle, upper, lower
    
    @staticmethod
    def macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD: line, signal, histogram."""
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram


class FeatureOrthogonalizer:
    """
    Feature Orthogonalization using PCA.
    
    Handles multicollinearity in feature sets by:
    1. Standardizing features
    2. Applying PCA to create uncorrelated components
    3. Selecting components that explain sufficient variance
    """
    
    def __init__(
        self,
        variance_threshold: float = 0.95,
        max_components: Optional[int] = None,
    ):
        self.variance_threshold = variance_threshold
        self.max_components = max_components
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.components_: Optional[np.ndarray] = None
        self.explained_variance_ratio_: Optional[np.ndarray] = None
        self.n_components_: int = 0
    
    def fit(self, features: np.ndarray) -> 'FeatureOrthogonalizer':
        """Fit the orthogonalizer to training data."""
        # Standardize
        self.mean_ = np.mean(features, axis=0)
        self.std_ = np.std(features, axis=0)
        self.std_[self.std_ == 0] = 1  # Prevent division by zero
        
        standardized = (features - self.mean_) / self.std_
        
        # Compute covariance matrix
        cov_matrix = np.cov(standardized, rowvar=False)
        
        # Eigenvalue decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # Sort by descending eigenvalue
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Select components
        total_var = np.sum(eigenvalues)
        explained_ratio = eigenvalues / total_var
        cumulative_ratio = np.cumsum(explained_ratio)
        
        # Find number of components
        n_components = np.argmax(cumulative_ratio >= self.variance_threshold) + 1
        if self.max_components:
            n_components = min(n_components, self.max_components)
        
        self.n_components_ = n_components
        self.components_ = eigenvectors[:, :n_components]
        self.explained_variance_ratio_ = explained_ratio[:n_components]
        
        logger.info(
            f"PCA: {n_components} components explain "
            f"{cumulative_ratio[n_components - 1]:.2%} variance"
        )
        
        return self
    
    def transform(self, features: np.ndarray) -> np.ndarray:
        """Transform features to orthogonal components."""
        if self.components_ is None:
            raise ValueError("Fit the orthogonalizer first")
        
        standardized = (features - self.mean_) / self.std_
        return standardized @ self.components_
    
    def fit_transform(self, features: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(features).transform(features)


class PurgedKFold:
    """
    Purged K-Fold Cross-Validation.
    
    Prevents data leakage in time series by:
    1. Purging: Removing samples that overlap with test set
    2. Embargo: Adding gap between train and test sets
    
    Essential for financial ML to avoid look-ahead bias.
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        purge_length: int = 0,
        embargo_length: int = 0,
    ):
        self.n_splits = n_splits
        self.purge_length = purge_length
        self.embargo_length = embargo_length
    
    def split(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
    ):
        """Generate train/test indices with purging and embargo."""
        n_samples = len(X)
        fold_size = n_samples // self.n_splits
        
        for i in range(self.n_splits):
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < self.n_splits - 1 else n_samples
            
            test_indices = np.arange(test_start, test_end)
            
            # Training indices with purging and embargo
            train_indices = []
            
            # Before test set
            train_end = test_start - self.purge_length - self.embargo_length
            if train_end > 0:
                train_indices.extend(range(0, train_end))
            
            # After test set
            train_start = test_end + self.embargo_length
            if train_start < n_samples:
                train_indices.extend(range(train_start, n_samples))
            
            if len(train_indices) > 0:
                yield np.array(train_indices), test_indices
