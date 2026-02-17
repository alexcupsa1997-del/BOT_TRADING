"""
engine/features.py - Real-Time Feature Engineering
==================================================

Calculates features incrementally for the ML Strategy.
MUST match logic in `analysis/src/quant/hft_features.py` (Basic Mode).
"""

import numpy as np
import pandas as pd
from collections import deque
from typing import Dict, List, Optional, Deque
from loguru import logger
from engine.events import Event, EventType

class FeatureCalculator:
    """
    Maintains a rolling window of price data to calculate features
    for the next inference step.
    """
    
    def __init__(self, window_size: int = 100):
        # We need enough history for the longest lookback (50) + safety
        self.window_size = window_size
        self.prices: Deque[float] = deque(maxlen=window_size)
        self.timestamps: Deque[float] = deque(maxlen=window_size)
        
        # Cache for expensive calculations
        self.df_cache: Optional[pd.DataFrame] = None
        
    def update(self, event: Event) -> Optional[np.ndarray]:
        """
        Updates state with new BAR event and returns feature vector.
        Returns None if not enough data.
        """
        if event.type != EventType.BAR:
            return None
            
        # 1. Update History
        close_price = float(event.data['close'])
        timestamp = event.data['timestamp']
        
        self.prices.append(close_price)
        self.timestamps.append(timestamp)
        
        # Need at least 50 bars for calculation + 1 for diff
        if len(self.prices) < 52:
            return None
            
        # 2. Convert to DataFrame
        df = pd.DataFrame({
            'trade_price': list(self.prices),
            'timestamp': list(self.timestamps)
        })
        
        # 3. Compute Features (Shared Logic)
        df = compute_features_batch(df)
        
        # 4. Extract Latest Row
        last_row = df.iloc[-1]

        
        # 4. Extract Latest Row
        last_row = df.iloc[-1]
        
        # Check for NaNs in latest row (shouldn't happen if window is full enough)
        feature_cols = [
            'feature_log_ret',
            'feature_vol_10', 'feature_vol_50',
            'feature_mom_10', 'feature_mom_50',
            'feature_rsi',
            'feature_macd', 'feature_macd_signal'
        ]
        
        # Ensure parity with training column order!
        # In trainer: feature_cols = [c for c in df.columns if 'feature_' in c]
        # The order in pandas depends on creation order.
        # We explicitly define extraction order here.
        # CRITICAL: This list MUST match the implicit order in goliath_trainer_v2 fallback.
        # Trainer creation order:
        # 1. log_ret
        # 2. vol_10
        # 3. vol_50
        # 4. mom_10
        # 5. mom_50
        # 6. rsi
        # 7. macd
        # 8. macd_signal
        
        features = last_row[feature_cols].values.astype(np.float32)
        
        if np.isnan(features).any():
            return None
            
        return features

class FeatureBuffer:
    """
    Buffers vectors to create sequences (e.g., last 64 vectors) for the transformer.
    """
    def __init__(self, sequence_length: int = 64, feature_dim: int = 8):
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.buffer = deque(maxlen=sequence_length)
        
    def add(self, feature_vector: np.ndarray):
        self.buffer.append(feature_vector)
        
    def is_ready(self) -> bool:
        return len(self.buffer) == self.sequence_length
        
    def get_sequence(self) -> np.ndarray:
        # Return shape (1, seq_len, features)
        return np.array(self.buffer, dtype=np.float32).reshape(1, self.sequence_length, self.feature_dim)

def compute_features_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Core feature calculation logic.
    Input DF must have: 'trade_price'
    Returns DF with added 'feature_*' columns.
    """
    df = df.copy()
    
    # Log Returns: log(P_t) - log(P_{t-1})
    df['feature_log_ret'] = np.log(df['trade_price']) - np.log(df['trade_price'].shift(1))
    
    # Volatility & Momentum
    for w in [10, 50]:
        df[f'feature_vol_{w}'] = df['feature_log_ret'].rolling(window=w).std()
        df[f'feature_mom_{w}'] = df['feature_log_ret'].rolling(window=w).sum()
        
    # RSI (14)
    delta = df['trade_price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1)
    df['feature_rsi'] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema12 = df['trade_price'].ewm(span=12, adjust=False).mean()
    ema26 = df['trade_price'].ewm(span=26, adjust=False).mean()
    df['feature_macd'] = ema12 - ema26
    df['feature_macd_signal'] = df['feature_macd'].ewm(span=9, adjust=False).mean()
    
    return df

