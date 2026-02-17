"""
tests/run_wfa.py
================

Verification script for WalkForwardEngine.
"""

import sys
from pathlib import Path
from decimal import Decimal
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from engine.data import PolarsDataFeed
from engine.walk_forward import WalkForwardEngine
from strategies.breakout import BreakoutStrategy
from loguru import logger

def generate_long_synthetic_data(csv_path: str):
    """Generate a longer sine wave price for WFA."""
    # 2 years of hourly data -> approx 17500 rows
    dates = pd.date_range(start="2022-01-01", end="2024-01-01", freq="h")
    n = len(dates)
    
    # Sine wave with changing regime?
    # Period 50 initially, then period 100
    x = np.linspace(0, 200 * np.pi, n)
    
    # Modulate frequency over time to test adaptability
    freq_mod = np.linspace(1, 0.5, n) # Slows down
    prices = 100 + 10 * np.sin(x * freq_mod)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": prices + 1,
        "low": prices - 1,
        "close": prices,
        "volume": 1000
    })
    df.to_csv(csv_path, index=False)
    return csv_path

def main():
    logger.info("Starting WFA Verification...")
    
    # 1. Create Data
    csv_path = "data/test_wfa.csv"
    Path("data").mkdir(exist_ok=True)
    generate_long_synthetic_data(csv_path)
    
    feed = PolarsDataFeed(csv_path, symbol="WFA_TEST")
    feed.load()
    
    # 2. Define Space
    param_space = {
        'period': {'type': 'int', 'low': 10, 'high': 100},
        'std_dev': {'type': 'float', 'low': 1.0, 'high': 4.0, 'step': 0.5}
    }
    
    # 3. Init WFA
    wfa = WalkForwardEngine(
        data_feed=feed,
        strategy_class=BreakoutStrategy,
        param_space=param_space,
        initial_capital=Decimal("10000.0")
    )
    
    # 4. Run WFA
    # Train: 90 days, Test: 30 days, Step: 30 days
    # This ensures no overlap in test sets, and rolling train window.
    report = wfa.run(
        train_window=pd.Timedelta(days=90),
        test_window=pd.Timedelta(days=30),
        step=pd.Timedelta(days=30),
        optimize_trials=5, # Keep low for speed
        optimize_metric="sharpe_ratio"
    )
    
    # Cleanup
    import os
    if os.path.exists(csv_path):
        os.remove(csv_path)

if __name__ == "__main__":
    main()
