"""
engine/reporting.py
===================

Performance reporting and metrics calculation for backtest results.
"""

from decimal import Decimal
import numpy as np
import pandas as pd
from loguru import logger
from typing import List, Dict, Any

class PerformanceReport:
    """Calculates performance metrics from trading history."""

    def __init__(self, history: List[Dict[str, Any]], initial_capital: Decimal):
        """
        Args:
            history: List of portfolio snapshots/trades or equity curve.
                     Currently expecting equity curve as list of dicts:
                     [{'timestamp': t, 'total_equity': e}, ...]
            initial_capital: Starting capital.
        """
        self.history = history
        self.initial_capital = float(initial_capital)
        self.equity_curve = self._prepare_equity_curve()

    def _prepare_equity_curve(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.history)
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('datetime', inplace=True)
            df.sort_index(inplace=True)
        
        # Convert equity to float for calculation
        df['equity'] = df['total_equity'].apply(float)
        df['returns'] = df['equity'].pct_change().fillna(0)
        return df

    def generate_metrics(self) -> Dict[str, Any]:
        """Calculates key performance metrics."""
        if self.equity_curve.empty:
            return {}

        df = self.equity_curve
        final_equity = df['equity'].iloc[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        # Sharpe Ratio (Assuming daily data implies 252 periods, but we might have minute data)
        # We need to detect frequency or assume a risk-free rate per period.
        # For simplicity, we calculate annualized sharpe if we know the duration.
        # Here we just calc basic Sharpe on the period returns.
        
        risk_free_rate = 0.0 # Simplified
        mean_return = df['returns'].mean()
        std_return = df['returns'].std()
        
        if std_return == 0:
            sharpe = 0.0
        else:
            sharpe = (mean_return - risk_free_rate) / std_return

        # Sortino (Downside risk)
        downside_returns = df.loc[df['returns'] < 0, 'returns']
        downside_std = downside_returns.std()
        if downside_std == 0:
            sortino = 0.0 # Or infinite?
        else:
            sortino = (mean_return - risk_free_rate) / downside_std

        # Max Drawdown
        df['cummax'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['cummax']) / df['cummax']
        max_drawdown = df['drawdown'].min()

        return {
            "Initial Capital": self.initial_capital,
            "Final Equity": final_equity,
            "Total Return (%)": total_return * 100,
            "Sharpe Ratio": sharpe, # Note: Not annualized
            "Sortino Ratio": sortino, # Note: Not annualized
            "Max Drawdown (%)": max_drawdown * 100
        }

    def print_report(self):
        metrics = self.generate_metrics()
        print("\n=== Backtest Performance Report ===")
        for k, v in metrics.items():
            if "Ratio" in k:
                print(f"{k}: {v:.4f}")
            elif "%" in k:
                print(f"{k}: {v:.2f}%")
            else:
                print(f"{k}: {v:.2f}")
        print("===================================\n")
