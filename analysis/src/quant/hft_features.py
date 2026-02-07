"""
HFT Feature Engineering Module (Goliath-Tensor Implementation)

This module implements high-frequency trading feature extraction logic
based on the "Goliath-Tensor" theory. It transforms raw tick data
(Bid/Ask/Trade) into stationary, geometrically meaningful tensors 
for Neural Network consumption.

References:
- analysis/STRATEGY_NOTES.md
"""

import numpy as np
import pandas as pd
from typing import List, Optional
from loguru import logger

class HFTFeatureEngineer:
    def __init__(self, use_logs: bool = True):
        """
        Args:
            use_logs: If True, uses logarithmic returns (recommended for ML).
        """
        self.use_logs = use_logs

    def load_data(self, parquet_path: str) -> pd.DataFrame:
        """Efficiently loads parquet data."""
        logger.info(f"Loading HFT data from {parquet_path}")
        try:
            df = pd.read_parquet(parquet_path)
            # Ensure chronological order
            df = df.sort_values('timestamp').reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    def compute_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pipeline that orchestrates the calculation of all HFT features.
        Returns a rich DataFrame with new feature columns.
        """
        initial_cols = len(df.columns)
        
        # 1. Micro-Structure / Order Book Features
        df = self.add_order_book_imbalance(df)
        df = self.add_spread_metrics(df)
        
        # 2. Price Action / Geometric Features
        df = self.add_returns_and_volatility(df)
        
        # 3. Technical Indicators (RSI, MACD)
        df = self.add_technical_indicators(df)
        
        # 4. Flow / Aggressor Features
        df = self.add_aggressor_flow(df)
        
        # 5. Cleanup - Only drop NaN on FEATURE columns, not all columns
        feature_cols = [c for c in df.columns if 'feature_' in c]
        df_clean = df.dropna(subset=feature_cols)
        
        new_cols = len(feature_cols)
        logger.info(f"Feature Engineering complete. Added {new_cols} new features.")
        logger.info(f"Data shape after cleaning: {df_clean.shape}")
        
        return df_clean

    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds classic technical indicators adapted for tick data.
        """
        # RSI (Relative Strength Index) - Window 14
        delta = df['trade_price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain / loss.replace(0, 1) # Avoid div by zero
        df['feature_rsi'] = 100 - (100 / (1 + rs))
        # Normalize RSI to 0-1 range roughly centered (or keep 0-100 and let Scaler handle it)
        # We'll let the StandardScaler handle it later.

        # MACD (12, 26, 9)
        ema12 = df['trade_price'].ewm(span=12, adjust=False).mean()
        ema26 = df['trade_price'].ewm(span=26, adjust=False).mean()
        df['feature_macd'] = ema12 - ema26
        df['feature_macd_signal'] = df['feature_macd'].ewm(span=9, adjust=False).mean()
        df['feature_macd_hist'] = df['feature_macd'] - df['feature_macd_signal']
        
        return df

    def add_order_book_imbalance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates Order Book Imbalance (OBI).
        OBI = (BidSize - AskSize) / (BidSize + AskSize)
        Range: [-1, 1] (1 = Full Buy Pressure, -1 = Full Sell Pressure)
        """
        # Avoid division by zero
        total_depth = df['bid_size'] + df['ask_size']
        total_depth = total_depth.replace(0, 1) # Safety clamp
        
        df['feature_obi'] = (df['bid_size'] - df['ask_size']) / total_depth
        return df

    def add_spread_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates relative spread (cost of liquidity).
        Spread_bps = (Ask - Bid) / MidPrice * 10000
        """
        mid_price = (df['bid_price'] + df['ask_price']) / 2
        spread_abs = df['ask_price'] - df['bid_price']
        
        df['feature_spread_bps'] = (spread_abs / mid_price) * 10000
        
        # Derivative: Is spread widening or tightening?
        df['feature_spread_change'] = df['feature_spread_bps'].diff()
        return df

    def add_returns_and_volatility(self, df: pd.DataFrame, windows: List[int] = [10, 50]):
        """
        Calculates log-returns and rolling micro-volatility.
        """
        # Log Returns (Stationary)
        if self.use_logs:
            # np.log(P_t / P_{t-1}) = np.log(P_t) - np.log(P_{t-1})
            df['feature_log_ret'] = np.log(df['trade_price']) - np.log(df['trade_price'].shift(1))
        else:
            df['feature_pct_ret'] = df['trade_price'].pct_change()
            
        target_ret_col = 'feature_log_ret' if self.use_logs else 'feature_pct_ret'

        # Rolling Volatility (Micro-burst detection)
        for w in windows:
            df[f'feature_vol_{w}'] = df[target_ret_col].rolling(window=w).std()
            
            # Momentum: Rolling Sum of returns
            df[f'feature_mom_{w}'] = df[target_ret_col].rolling(window=w).sum()
            
        return df

    def add_aggressor_flow(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """
        Calculates Net Aggressor Flow using the 'aggressor_side' flag.
        +1 = Buyer initiated, -1 = Seller initiated.
        """
        # Raw Flow: Volume * Side
        df['signed_volume'] = df['volume'] * df['aggressor_side']
        
        # Cumulative Flow Delta (CVD) - Rolling
        df['feature_flow_imbalance'] = df['signed_volume'].rolling(window=window).sum()
        
        # Normalized Flow (Flow / Total Volume) to make it stationary
        total_vol = df['volume'].rolling(window=window).sum()
        df['feature_flow_ratio'] = df['feature_flow_imbalance'] / total_vol.replace(0, 1)
        
        # Drop temporary column
        df = df.drop(columns=['signed_volume'])
        return df

if __name__ == "__main__":
    # Test execution
    try:
        engineer = HFTFeatureEngineer()
        df_raw = engineer.load_data('data/synthetic_hft_ticks.parquet')
        df_features = engineer.compute_all_features(df_raw)
        
        print("\n--- Feature Preview ---")
        print(df_features.filter(like='feature_').head())
        print("\n--- Statistics ---")
        print(df_features.filter(like='feature_').describe().T)
        
    except FileNotFoundError:
        print("Please run 'generate_hft_data.py' first to create synthetic data.")
