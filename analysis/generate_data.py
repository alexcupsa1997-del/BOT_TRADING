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

if __name__ == "__main__":
    # Simulate 1 Year of Data (approx 1 tick per minute for speed, or more)
    # For backtest speed, let's generate 1 month of "Medium Frequency" data (e.g. 1 tick every 10 sec)
    # 1 Month = 30 days
    # Ticks per day = 8640 (10 sec)
    
    # Let's do 1 Year of 1-minute data for the "Strategy" test
    # 365 * 1440 = 525,600 ticks
    
    output_path = "analysis/data/synthetic_market.parquet"
    
    generate_gbm_data(
        symbol_id=1,
        start_price=45000.0, # BTC-ish
        mu=0.1,              # 10% Annual Drift (Bull market)
        sigma=0.5,           # 50% Annual Volatility (Crypto style)
        duration_days=365,
        ticks_per_day=1440,  # 1 tick per minute
        output_file=output_path
    )
