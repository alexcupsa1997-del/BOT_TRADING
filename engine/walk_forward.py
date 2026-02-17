"""
engine/walk_forward.py
======================

Walk-Forward Analysis Engine.
Performs rolling window optimization and validation.
"""

import pandas as pd
from decimal import Decimal
from typing import Dict, Any, Type, List
from loguru import logger
import polars as pl

from engine.data import PolarsDataFeed
from engine.strategy import Strategy
from engine.hyperopt_engine import HyperoptEngine
from engine.backtest_engine import BacktestEngine
from engine.reporting import PerformanceReport

class WalkForwardEngine:
    """
    Manages Walk-Forward Analysis (WFA).
    
    Splits data into overlapping Train/Test windows.
    1. Optimize on Train Window.
    2. Test best params on Test Window.
    3. Roll forward.
    4. Aggregates results to form a continuous equity curve of "out-of-sample" performance.
    """
    
    def __init__(self, 
                 data_feed: PolarsDataFeed, 
                 strategy_class: Type[Strategy], 
                 param_space: Dict[str, Any],
                 initial_capital: Decimal = Decimal("100000.0")):
        
        self.data_feed = data_feed
        self.strategy_class = strategy_class
        self.param_space = param_space
        self.initial_capital = initial_capital
        
        # Ensure data is loaded
        if self.data_feed.df is None:
            raise ValueError("DataFeed must be loaded before Walk-Forward Analysis.")
            
        # Sort data by timestamp just in case
        self.data_feed.df = self.data_feed.df.sort("timestamp")
        
    def run(self, 
            train_window: pd.Timedelta, 
            test_window: pd.Timedelta, 
            step: pd.Timedelta,
            optimize_trials: int = 10,
            optimize_metric: str = "sharpe_ratio") -> PerformanceReport:
        
        logger.info("Starting Walk-Forward Analysis...")
        
        # Determine Date Range
        timestamps = self.data_feed.df["timestamp"]
        min_date = pd.to_datetime(timestamps.min(), unit='s') if isinstance(timestamps[0], int) else pd.to_datetime(timestamps.min()) # Handle int ns or datetime
        max_date = pd.to_datetime(timestamps.max(), unit='s') if isinstance(timestamps[-1], int) else pd.to_datetime(timestamps.max())
        
        logger.info(f"Data Range: {min_date} to {max_date}")
        
        current_start = min_date
        
        aggregated_history = []
        # We need to track cash specifically to chain the equity
        current_capital = self.initial_capital
        
        wfa_stats = []
        
        while True:
            train_end = current_start + train_window
            test_end = train_end + test_window
            
            if test_end > max_date:
                break
                
            logger.info(f"Window: Train [{current_start} - {train_end}] | Test [{train_end} - {test_end}]")
            
            # 1. Prepare Data Feeds
            # Convert back to whatever format Polars expects if needed, or pass datetime
            # Polars filter expects the native type.
            # If Polars timestamp is int (ns), we need to convert.
            # Usually Polars read_csv guesses. Let's assume it handles datetime comparison if column is datetime.
            # If not, we might need to cast.
            
            train_feed = self.data_feed.slice(current_start, train_end)
            test_feed = self.data_feed.slice(train_end, test_end)
            
            if train_feed.df.height < 10 or test_feed.df.height < 10:
                logger.warning("Insufficient data in window, skipping.")
                current_start += step
                continue

            # 2. Optimize on Train
            logger.info("  Optimizing...")
            hyperopt = HyperoptEngine(train_feed, initial_capital=self.initial_capital)
            # Suppress logs?
            best_params = hyperopt.optimize(
                self.strategy_class, 
                self.param_space, 
                n_trials=optimize_trials, 
                metric=optimize_metric
            )
            logger.info(f"  Best Params: {best_params}")
            
            # 3. Test on Test (Out-of-Sample)
            logger.info("  Testing OOS...")
            # We chain capital: The OOS test starts with the capital we have currently
            engine = BacktestEngine(initial_cash=current_capital, verbose=True)
            engine.add_data_feed(test_feed)
            
            # Init strategy with best params
            strat = self.strategy_class(engine, **best_params)
            engine.add_strategy(strat)
            
            report = engine.run()
            
            # 4. Aggregate Results
            # We take the history chunks.
            # Note: timestamps must be strictly increasing.
            aggregated_history.extend(report.history)
            
            # Update current capital for next window
            # The engine.run() updates engine.cash and engine.portfolio.
            # But the final equity is what matters.
            # We assume closed positions? No, WFA usually assumes we close out or carry over.
            # Simplifying: We assume we just carry the cash/equity value.
            # report.history[-1] contains {'total_equity': ...}
            if report.history:
                current_capital = report.history[-1]['total_equity']
            
            metrics = report.generate_metrics()
            wfa_stats.append({
                "window_start": train_end,
                "window_end": test_end,
                "params": best_params,
                "return": metrics.get("Total Return (%)", 0.0)
            })
            
            # Roll forward
            current_start += step
            
        logger.info("Walk-Forward Analysis Finished.")
        
        final_report = PerformanceReport(aggregated_history, self.initial_capital)
        final_report.print_report()
        
        return final_report
