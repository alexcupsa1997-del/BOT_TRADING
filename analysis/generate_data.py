import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
import time

def generate_gbm_data(
    symbol_id: int,
    start_price: float,
    mu: float,
    sigma: float,
    duration_days: int,
    ticks_per_day: int,
    output_file: str
):
    """
    Generates synthetic tick data using Geometric Brownian Motion.
    
    Parameters:
    - symbol_id: ID of the instrument
    - start_price: Initial price
    - mu: Drift (trend)
    - sigma: Volatility
    - duration_days: Number of days to simulate
    - ticks_per_day: Number of ticks per day
    """
    print(f"Generating synthetic data for Symbol {symbol_id}...")
    
    n_ticks = duration_days * ticks_per_day
    dt = 1.0 / ticks_per_day # Time step
    
    # 1. Generate Brownian Motion
    # random shocks
    shocks = np.random.normal(0, np.sqrt(dt), n_ticks)
    
    # Cumulative sum for Brownian path
    brownian_motion = np.cumsum(shocks)
    
    # GBM Formula: S_t = S_0 * exp((mu - 0.5 * sigma^2)*t + sigma * W_t)
    # t vector
    t = np.linspace(0, duration_days, n_ticks)
    
    # Calculate Prices
    prices = start_price * np.exp((mu - 0.5 * sigma**2) * t + sigma * brownian_motion)
    
    # 2. Simulate Bid/Ask Spread (Microstructure)
    # Spread is random between 0.01% and 0.05% of price
    spread_pct = np.random.uniform(0.0001, 0.0005, n_ticks)
    half_spread = (prices * spread_pct) / 2
    
    bids = prices - half_spread
    asks = prices + half_spread
    
    # 3. Timestamps
    # Start from 2025-01-01
    start_ts = pd.Timestamp("2025-01-01").value // 10**6 # millis
    # Distribute ticks evenly (simplification, real markets have clusters)
    # millisecond increments
    time_increments = np.linspace(0, duration_days * 24 * 3600 * 1000, n_ticks).astype(np.int64)
    timestamps = start_ts + time_increments
    
    # 4. Volume
    # Log-normal distribution for volume
    volumes = np.random.lognormal(mean=0.0, sigma=1.0, size=n_ticks)
    
    # 5. Create DataFrame
    df = pd.DataFrame({
        'symbol_id': np.full(n_ticks, symbol_id, dtype='int64'),
        'timestamp': timestamps,
        'bid': bids,
        'ask': asks,
        'volume': volumes,
        'flags': np.zeros(n_ticks, dtype='int32') # 0 = Normal
    })
    
    # 6. Save to Parquet
    print(f"Saving {n_ticks} rows to {output_file}...")
    
    # Create directory if needed
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(output_file, engine='pyarrow')
    print("Done.")

def generate_ohlcv_data(
    symbol: str,
    start_price: float,
    mu: float,
    sigma: float,
    duration_days: int,
    output_path: str
):
    """Generates synthetic 1-minute OHLCV data."""
    print(f"Generating OHLCV data for {symbol}...")
    
    # 1 Minute bars
    minutes = duration_days * 24 * 60
    dt = 1.0 / (24 * 60)
    
    # GBM for Close Prices
    shocks = np.random.normal(0, np.sqrt(dt), minutes)
    brownian = np.cumsum(shocks)
    t = np.linspace(0, duration_days, minutes)
    close_prices = start_price * np.exp((mu - 0.5 * sigma**2) * t + sigma * brownian)
    
    # High/Low/Open derived from Close
    # Simplified intra-bar movement
    opens = np.roll(close_prices, 1)
    opens[0] = start_price
    
    highs = np.maximum(opens, close_prices) + np.random.uniform(0, start_price*0.002, minutes)
    lows = np.minimum(opens, close_prices) - np.random.uniform(0, start_price*0.002, minutes)
    
    # Timestamps
    start_ts = pd.Timestamp("2024-01-01").value // 10**9 # seconds
    timestamps = start_ts + np.arange(minutes) * 60
    
    # Volume
    volumes = np.random.lognormal(mean=2.0, sigma=0.5, size=minutes)
    
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps, unit='s'), # Polars/Pandas compat
        "open": opens,
        "high": highs,
        "low": lows,
        "close": close_prices,
        "trade_price": close_prices, # For feature calc parity
        "volume": volumes,
        "symbol": symbol
    })
    
    # Ensure directory
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Save
    print(f"Saving {minutes} rows to {output_path}...")
    df.to_parquet(output_path)
    print("Done.")

if __name__ == "__main__":
    # Generate 1-minute OHLCV for Goliath Training
    generate_ohlcv_data(
        symbol="BTCUSD",
        start_price=45000.0,
        mu=0.1,
        sigma=0.5,
        duration_days=30, # 1 Month
        output_path="data/raw/BTCUSD/1m/synthetic.parquet"
    )

