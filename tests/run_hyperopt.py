"""
tests/run_hyperopt.py
=====================

Verification script for HyperoptEngine.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from engine.data import PolarsDataFeed
from engine.hyperopt_engine import HyperoptEngine
from strategies.breakout import BreakoutStrategy
from loguru import logger
import pandas as pd
import numpy as np

def generate_synthetic_data(csv_path: str):
    """Generate a sine wave price for testing."""
    dates = pd.date_range(start="2023-01-01", periods=1000, freq="h")
    # Sine wave with period 50
    x = np.linspace(0, 40 * np.pi, 1000)
    prices = 100 + 10 * np.sin(x)
    
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
    logger.info("Starting Hyperopt Verification...")
    
    # 1. Create Data
    csv_path = "data/test_sine.csv"
    Path("data").mkdir(exist_ok=True)
    generate_synthetic_data(csv_path)
    
    feed = PolarsDataFeed(csv_path, symbol="SINE")
    feed.load()
    
    # 2. Init Hyperopt
    optimizer = HyperoptEngine(data_feed=feed, initial_capital=Decimal("10000.0"))
    
    # 3. Define Space
    # Breakout strategy has 'period' and 'std_dev'.
    # Sine wave has period approx 50 steps (1000 steps / 20 cycles = 50).
    # Best period should be related to this.
    param_space = {
        'period': {'type': 'int', 'low': 10, 'high': 100},
        'std_dev': {'type': 'float', 'low': 1.0, 'high': 4.0, 'step': 0.1}
    }
    
    # 4. Run Optimization
    logger.info("Running optimization (5 trials)...")
    best_params = optimizer.optimize(
        strategy_class=BreakoutStrategy,
        param_space=param_space,
        n_trials=5,
        metric="sharpe_ratio",
        direction="maximize"
    )
    
    logger.success(f"Best Params found: {best_params}")
    
    # Cleanup
    import os
    if os.path.exists(csv_path):
        os.remove(csv_path)

if __name__ == "__main__":
    main()
