import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import os

OUTPUT_DIR = 'data'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_base_structure(num_ticks, start_price=100.0):
    """Creates the base timestamps and HFT columns structure."""
    start_time = datetime.now()
    inter_arrival = np.random.exponential(scale=0.01, size=num_ticks)
    timestamps = [start_time + timedelta(seconds=t) for t in np.cumsum(inter_arrival)]
    
    # Base columns placeholders
    df = pd.DataFrame({'timestamp': timestamps})
    df['bid_size'] = np.random.randint(1, 100, size=num_ticks)
    df['ask_size'] = np.random.randint(1, 100, size=num_ticks)
    df['volume'] = np.random.randint(1, 10, size=num_ticks)
    df['aggressor_side'] = np.random.choice([1, -1], size=num_ticks)
    return df

def save_parquet(df, filename):
    table = pa.Table.from_pandas(df)
    pq.write_table(table, os.path.join(OUTPUT_DIR, filename), compression='SNAPPY')
    print(f"Generated {filename} ({len(df)} ticks)")

def generate_bull_trend(num_ticks=20000):
    """Scenario: Strong Uptrend with high buy pressure."""
    df = generate_base_structure(num_ticks)
    
    # Deterministic Trend + Random Noise
    t = np.linspace(0, 10, num_ticks)
    price_path = 100 + (t * 2) + np.random.normal(0, 0.2, num_ticks) # Steady climb
    
    # Bias inputs to help model learn
    df['bid_size'] = df['bid_size'] * 2 # Higher bid support
    df['aggressor_side'] = np.random.choice([1, -1], size=num_ticks, p=[0.7, 0.3]) # More buyers
    
    # Set prices
    spread = 0.01
    df['trade_price'] = price_path
    df['bid_price'] = price_path - (spread/2)
    df['ask_price'] = price_path + (spread/2)
    
    save_parquet(df, 'scenario_bull_trend.parquet')

def generate_choppy_range(num_ticks=20000):
    """Scenario: Sideways market (Mean Reversion)."""
    df = generate_base_structure(num_ticks)
    
    # Sine wave + Noise
    t = np.linspace(0, 20, num_ticks)
    price_path = 100 + np.sin(t) + np.random.normal(0, 0.1, num_ticks)
    
    # Balanced inputs
    df['aggressor_side'] = np.random.choice([1, -1], size=num_ticks, p=[0.5, 0.5])
    
    spread = 0.02 # Wider spread in chop
    df['trade_price'] = price_path
    df['bid_price'] = price_path - (spread/2)
    df['ask_price'] = price_path + (spread/2)
    
    save_parquet(df, 'scenario_chop_range.parquet')

def generate_flash_crash(num_ticks=10000):
    """Scenario: Sudden collapse."""
    df = generate_base_structure(num_ticks)
    
    # Flat then Drop
    price_path = np.ones(num_ticks) * 100
    crash_start = int(num_ticks * 0.7)
    
    # Normal until crash
    price_path[:crash_start] += np.random.normal(0, 0.05, crash_start)
    # Crash!
    price_path[crash_start:] = 100 - np.linspace(0, 10, num_ticks - crash_start)
    
    # Panic signals
    df.loc[crash_start:, 'ask_size'] = df.loc[crash_start:, 'ask_size'] * 5 # Massive sell wall
    df.loc[crash_start:, 'aggressor_side'] = -1 # All sellers
    df.loc[crash_start:, 'volume'] = df.loc[crash_start:, 'volume'] * 10 # Panic volume
    
    spread = 0.05 # Widening spread
    df['trade_price'] = price_path
    df['bid_price'] = price_path - spread
    df['ask_price'] = price_path
    
    save_parquet(df, 'scenario_flash_crash.parquet')

if __name__ == "__main__":
    print("Generating Training Scenarios...")
    generate_bull_trend()
    generate_choppy_range()
    generate_flash_crash()
    print("Done.")
