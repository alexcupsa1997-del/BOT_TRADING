import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import os

OUTPUT_FILE = 'data/massive_mixed_scenario.parquet'

def generate_segment(num_ticks, mode='range', start_price=100.0, start_time=None):
    if start_time is None:
        start_time = datetime.now()
        
    # Time deltas
    inter_arrival = np.random.exponential(scale=0.005, size=num_ticks) # Faster 5ms
    timestamps = [start_time + timedelta(seconds=t) for t in np.cumsum(inter_arrival)]
    
    # Base Price Path
    noise = np.random.normal(0, 0.05, num_ticks)
    
    if mode == 'bull':
        trend = np.linspace(0, 5, num_ticks) # Up $5
        price_path = start_price + trend + noise
        aggressor_prob = 0.65 # Buyers
    elif mode == 'bear':
        trend = np.linspace(0, -5, num_ticks) # Down $5
        price_path = start_price + trend + noise
        aggressor_prob = 0.35 # Sellers
    elif mode == 'crash':
        trend = np.linspace(0, -15, num_ticks) # Crash $15
        noise = np.random.normal(0, 0.2, num_ticks) # High vol
        price_path = start_price + trend + noise
        aggressor_prob = 0.10 # Panic Sellers
    else: # range
        trend = np.sin(np.linspace(0, 10, num_ticks)) * 0.5
        price_path = start_price + trend + noise
        aggressor_prob = 0.50
        
    # Build DF
    df = pd.DataFrame({'timestamp': timestamps})
    df['trade_price'] = price_path
    
    # Spread dynamics based on volatility
    if mode == 'crash':
        spread = 0.10
    else:
        spread = 0.01
        
    df['bid_price'] = df['trade_price'] - (spread/2)
    df['ask_price'] = df['trade_price'] + (spread/2)
    
    # Order Book Depth
    base_depth = 100
    if mode == 'crash': base_depth = 10 # Liquidity dries up
    
    df['bid_size'] = np.random.gamma(2, base_depth, size=num_ticks).astype(int)
    df['ask_size'] = np.random.gamma(2, base_depth, size=num_ticks).astype(int)
    
    # Aggressor
    df['aggressor_side'] = np.random.choice([1, -1], size=num_ticks, p=[aggressor_prob, 1-aggressor_prob])
    df['volume'] = np.random.randint(1, 10, size=num_ticks)
    
    return df

def generate_massive_dataset():
    print("Generating Massive Mixed Regime Dataset (200k ticks)...")
    
    segments = []
    current_price = 100.0
    current_time = datetime.now()
    
    # Sequence of regimes to simulate a "Crazy Day"
    regimes = ['range', 'bull', 'range', 'bear', 'crash', 'bear', 'range', 'bull']
    ticks_per_segment = 25000
    
    for mode in regimes:
        print(f"  -> Generating segment: {mode}")
        df = generate_segment(ticks_per_segment, mode, current_price, current_time)
        
        segments.append(df)
        
        # Update state for next segment
        current_price = df['trade_price'].iloc[-1]
        current_time = df['timestamp'].iloc[-1]
        
    full_df = pd.concat(segments, ignore_index=True)
    
    # Save
    table = pa.Table.from_pandas(full_df)
    pq.write_table(table, OUTPUT_FILE, compression='SNAPPY')
    print(f"Saved {OUTPUT_FILE}: {len(full_df)} ticks")

if __name__ == "__main__":
    generate_massive_dataset()
