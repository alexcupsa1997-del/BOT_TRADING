import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta

def generate_hft_synthetic_data(num_ticks=10000, output_file='data/synthetic_hft_ticks.parquet'):
    """
    Generates high-fidelity synthetic HFT tick data for testing feature engineering.
    Includes explicit Bid/Ask columns for Order Book Imbalance calculation.
    """
    print(f"Generating {num_ticks} synthetic HFT ticks...")
    
    # 1. Generate Timestamps (Non-uniform distribution to simulate bursts)
    start_time = datetime.now()
    # Use exponential distribution for inter-arrival times (Poisson process approximation)
    inter_arrival_times = np.random.exponential(scale=0.01, size=num_ticks) # Avg 10ms
    time_deltas = np.cumsum(inter_arrival_times)
    timestamps = [start_time + timedelta(seconds=t) for t in time_deltas]
    
    # 2. Generate Price Process (Geometric Brownian Motion + Micro-noise)
    price_0 = 100.0
    drift = 0.0
    volatility = 0.0001 # Micro-volatility
    
    # Random walk steps
    returns = np.random.normal(loc=drift, scale=volatility, size=num_ticks)
    price_path = price_0 * np.exp(np.cumsum(returns))
    
    # 3. Generate Bid/Ask Spread & Depths
    # Spread usually 1-2 ticks, varies with volatility
    spreads = np.random.choice([0.01, 0.02, 0.03], size=num_ticks, p=[0.7, 0.2, 0.1])
    
    bid_prices = price_path - (spreads / 2)
    ask_prices = price_path + (spreads / 2)
    
    # Order Book Depths (Gamma distribution for realistic volume)
    bid_sizes = np.random.gamma(shape=2.0, scale=100.0, size=num_ticks).astype(int)
    ask_sizes = np.random.gamma(shape=2.0, scale=100.0, size=num_ticks).astype(int)
    
    # Trade Volume (subset of depth)
    volumes = np.minimum(bid_sizes, ask_sizes) // np.random.randint(1, 10, size=num_ticks)
    volumes = np.maximum(volumes, 1) # At least 1 lot
    
    # Flags (1=Buy, -1=Sell) driven by aggressor
    aggressor_flags = np.random.choice([1, -1], size=num_ticks)

    # 4. Construct DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'bid_price': bid_prices,
        'ask_price': ask_prices,
        'bid_size': bid_sizes,
        'ask_size': ask_sizes,
        'trade_price': np.where(aggressor_flags == 1, ask_prices, bid_prices), # Aggressor logic
        'volume': volumes,
        'aggressor_side': aggressor_flags
    })
    
    # Ensure types are optimized
    df['timestamp'] = df['timestamp'].astype('datetime64[ns]')
    for col in ['bid_price', 'ask_price', 'trade_price']:
        df[col] = df[col].astype('float64')
    for col in ['bid_size', 'ask_size', 'volume', 'aggressor_side']:
        df[col] = df[col].astype('int32')

    # 5. Write to Parquet
    table = pa.Table.from_pandas(df)
    pq.write_table(table, output_file, compression='SNAPPY')
    
    print(f"Saved to {output_file}. Schema:")
    print(df.dtypes)
    return df

if __name__ == "__main__":
    generate_hft_synthetic_data()
