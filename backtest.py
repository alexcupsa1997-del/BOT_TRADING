#!/usr/bin/env python3
"""
backtest.py
===========

Main entry point for running backtests.
Usage:
    python backtest.py --strategy breakout --symbol BTCUSD --days 30
"""

import argparse
import sys
import os
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from loguru import logger
from engine.backtest_engine import BacktestEngine
from engine.data import PolarsDataFeed
from engine.events import EventType

# Import Strategies
from strategies.breakout import BreakoutStrategy
from strategies.grid import SimpleGridStrategy

def main():
    parser = argparse.ArgumentParser(description="GOLIATH Backtest Runner")
    parser.add_argument("--strategy", type=str, required=True, choices=["breakout", "grid"], help="Strategy to run")
    parser.add_argument("--symbol", type=str, default="BTCUSD", help="Symbol to backtest")
    parser.add_argument("--days", type=int, default=30, help="Number of days of history to load")
    parser.add_argument("--csv", type=str, help="Path to CSV data file (optional override)")
    
    # Strategy specific args
    parser.add_argument("--period", type=int, default=20, help="Period for Breakout Strategy")
    parser.add_argument("--std_dev", type=float, default=2.0, help="StdDev for Breakout Strategy")
    parser.add_argument("--grid_step", type=float, default=100.0, help="Grid Step for Grid Strategy")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Backtest: {args.strategy.upper()} on {args.symbol}")
    
    # 1. Initialize Engine
    engine = BacktestEngine()
    
    # 2. Setup Data Feed
    # For now, we generate synthetic data if no CSV provided, or we can use PolarsDataFeed with a CSV.
    # We don't have a plugged-in historical data downloader in this script yet.
    # So we will create ANY dummy CSV if not exists, or error out.
    
    data_path = args.csv
    if not data_path:
        # Check for default data file
        default_file = f"data/{args.symbol}_1h.csv"
        if os.path.exists(default_file):
            data_path = default_file
        else:
            # Generate synthetic data for testing if no file found
            logger.warning(f"No data file found. Generating synthetic data for {args.symbol}...")
            # We can't easily generate synthetic data for PolarsDataFeed without writing a file.
            # Let's write a temporary one.
            import numpy as np
            import pandas as pd
            
            dates = pd.date_range(end=pd.Timestamp.now(), periods=args.days*24, freq='h')
            # random walk
            price = 50000 + np.cumsum(np.random.randn(len(dates)) * 100)
            
            df = pd.DataFrame({
                'time': dates.astype(int) // 10**9, # Unix seconds
                'open': price,
                'high': price + 50,
                'low': price - 50,
                'close': price,
                'volume': 1000
            })
            temp_file = "temp_synthetic_data.csv"
            df.to_csv(temp_file, index=False)
            data_path = temp_file
            logger.info(f"Generated synthetic data at {temp_file}")
            
    logger.info(f"Loading data from {data_path}")
    feed = PolarsDataFeed(data_path, args.symbol)
    engine.add_data_feed(feed)
    
    # 3. Setup Strategy
    if args.strategy == "breakout":
        strategy = BreakoutStrategy(engine, period=args.period, std_dev=args.std_dev)
    elif args.strategy == "grid":
        strategy = SimpleGridStrategy(engine, grid_step=args.grid_step)
        
    engine.add_strategy(strategy)
    
    # 4. Run
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("Backtest interrupted.")
    except Exception as e:
        logger.exception(f"Backtest failed: {e}")
        
if __name__ == "__main__":
    main()
