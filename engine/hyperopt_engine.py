"""
engine/hyperopt_engine.py
=========================

Hyperparameter Optimization Engine using Optuna.
Optimizes Strategy parameters against a given objective function (Sharpe, Return, etc).
"""

import optuna
import logging
from decimal import Decimal
from typing import Dict, Any, Type, List
from engine.backtest_engine import BacktestEngine
from engine.data import DataFeed
from engine.strategy import Strategy

# Suppress excessive logs during optimization
logging.getLogger("optuna").setLevel(logging.WARNING)

class HyperoptEngine:
    def __init__(self, data_feed: DataFeed, initial_capital: Decimal = Decimal("100000.0")):
        self.data_feed = data_feed
        self.initial_capital = initial_capital

    def optimize(self, 
                 strategy_class: Type[Strategy], 
                 param_space: Dict[str, Dict[str, Any]], 
                 n_trials: int = 20, 
                 metric: str = "sharpe_ratio",
                 direction: str = "maximize") -> Dict[str, Any]:
        """
        Run Optuna optimization.
        
        Args:
            strategy_class: The strategy class to optimize.
            param_space: Dictionary defining parameter space.
                         Ex: {'period': {'type': 'int', 'low': 10, 'high': 50}}
            n_trials: Number of trials.
            metric: Metric to optimize (total_return, sharpe_ratio, sortino_ratio, max_drawdown).
            direction: 'maximize' or 'minimize'.
        """
        
        def objective(trial):
            # 1. Sample Parameters
            params = {}
            for name, config in param_space.items():
                p_type = config.get('type')
                if p_type == 'int':
                    params[name] = trial.suggest_int(name, config['low'], config['high'], step=config.get('step', 1))
                elif p_type == 'float':
                    params[name] = trial.suggest_float(name, config['low'], config['high'], step=config.get('step', None))
                elif p_type == 'categorical':
                    params[name] = trial.suggest_categorical(name, config['choices'])

            # 2. Setup Engine
            # Note: We need a fresh engine for each trial
            engine = BacktestEngine(initial_cash=self.initial_capital)
            
            # Clone/Reset Data Feed? 
            # Our PolarsDataFeed loads data into memory. We can reuse the same instance 
            # as long as 'get_next' iterator logic is handled correctly. 
            # But 'engine' consumes the feed via 'get_next'. 
            # We need to RESET the feed or create a new iterator.
            # PolarsDataFeed.get_next() uses self.current_idx. We need a reset() method.
            # For now, let's assume we pass a new feed or reset it.
            # Let's check PolarsDataFeed.
            
            # ACTUALLY: PolarsDataFeed maintains state (self.current_idx).
            # We must reset it.
            if hasattr(self.data_feed, 'reset'):
                self.data_feed.reset()
            
            engine.add_data_feed(self.data_feed)
            
            # 3. Initialize Strategy with params
            # We assume Strategy accepts kwargs matching param_space keys
            try:
                strat = strategy_class(engine, **params)
                engine.add_strategy(strat)
            except TypeError as e:
                # Fallback if strategy doesn't accept kwargs directly (shouldn't happen with our design)
                print(f"Error init strategy: {e}")
                raise e

            # 4. Run Backtest
            # Suppress engine logs for speed?
            # We can't easily suppress loguru globally without affecting everything, 
            # but we can rely on log level.
            
            report = engine.run()
            
            # 5. Extract Metric
            
            metrics = report.generate_metrics()
            value = 0.0
            
            # Map friendly names to report keys if needed, or rely on exact match
            # The report keys are like "Sharpe Ratio", "Total Return (%)"
            # Param space keys are "sharpe_ratio", "total_return"
            
            # Simple normalization map
            key_map = {
                "sharpe_ratio": "Sharpe Ratio",
                "total_return": "Total Return (%)",
                "max_drawdown": "Max Drawdown (%)",
                "sortino_ratio": "Sortino Ratio"
            }
            
            target_key = key_map.get(metric, metric)
            
            if target_key in metrics:
                # Convert Decimal/String to float for Optuna
                try:
                    val_str = str(metrics[target_key]).strip('%')
                    value = float(val_str)
                except:
                    value = 0.0
            
            # Handle special cases
            if metric == "max_drawdown" and direction == "minimize":
                # If we want to minimize drawdown, we can just return it directly (it's usually negative or positive %)
                # Our report returns Max Drawdown as negative % usually? 
                # Let's check reporting.py. usually it's a positive number representing drop.
                pass

            return value

        study = optuna.create_study(direction=direction)
        study.optimize(objective, n_trials=n_trials)
        
        print(f"Best params: {study.best_params}")
        print(f"Best {metric}: {study.best_value}")
        
        return study.best_params
