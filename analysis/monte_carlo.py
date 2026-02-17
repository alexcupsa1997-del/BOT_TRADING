"""
analysis/monte_carlo.py - Robustness Analysis
=============================================

Performs Monte Carlo simulations on a sequence of trade returns
to estimate the probability of drawdown and ruin.

Usage:
    python analysis/monte_carlo.py --trades my_trades.csv
"""

import numpy as np
import pandas as pd
import argparse
import sys
from loguru import logger
from typing import List, Dict

def run_monte_carlo(trades: np.ndarray, 
                   start_balance: float, 
                   simulations: int = 1000, 
                   samples_per_sim: int = None) -> Dict:
    """
    Runs MC simulation by shuffling trades.
    
    Args:
        trades: Array of PnL values (absolute or %)
        start_balance: Initial Account Value
        simulations: Number of paths to generate
        samples_per_sim: Length of each path (defaults to len(trades))
        
    Returns:
        Dict with risk metrics.
    """
    if len(trades) < 10:
        logger.warning("Not enough trades for robust MC.")
        
    n_trades = len(trades)
    if samples_per_sim is None:
        samples_per_sim = n_trades
        
    logger.info(f"Running {simulations} simulations with {samples_per_sim} trades each...")
    
    final_eqs = []
    max_dDs = []
    ruin_count = 0
    
    paths = np.zeros((simulations, samples_per_sim + 1))
    paths[:, 0] = start_balance
    
    for i in range(simulations):
        # Bootstrap resampling (with replacement) to simulate different market regimes
        # Or simple shuffling (without replacement) to test sequence risk?
        # Standard MC often uses resampling.
        random_indices = np.random.randint(0, n_trades, size=samples_per_sim)
        resampled_pnl = trades[random_indices]
        
        # Calculate Equity Curve
        equity_curve = np.zeros(samples_per_sim + 1)
        equity_curve[0] = start_balance
        equity_curve[1:] = start_balance + np.cumsum(resampled_pnl)
        
        paths[i, :] = equity_curve
        
        # Final Equity
        final_eq = equity_curve[-1]
        final_eqs.append(final_eq)
        
        # Drawdown
        peaks = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - peaks) / peaks
        max_dd = np.min(drawdowns) # Negative value
        max_dDs.append(max_dd)
        
        # Ruin (Equity <= 0)
        if np.any(equity_curve <= 0):
            ruin_count += 1
            
    # Metrics
    final_eqs = np.array(final_eqs)
    max_dDs = np.array(max_dDs) # These are negative percentages, e.g. -0.05
    
    metrics = {
        "median_equity": np.median(final_eqs),
        "worst_case_equity": np.percentile(final_eqs, 5), # 5th percentile
        "best_case_equity": np.percentile(final_eqs, 95),
        "median_max_dd": np.median(max_dDs) * 100,
        "worst_case_max_dd": np.percentile(max_dDs, 5) * 100, # 5th percentile (most negative)
        "ruin_probability": (ruin_count / simulations) * 100
    }
    
    return metrics

def simulate_dummy_data():
    """Generates dummy trade data for testing."""
    # 50% win rate, 1:1.5 Risk:Reward
    wins = np.random.normal(150, 20, 50)
    losses = np.random.normal(-100, 10, 50)
    trades = np.concatenate([wins, losses])
    np.random.shuffle(trades)
    return trades

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo Analysis")
    parser.add_argument("--balance", type=float, default=10000.0, help="Initial Account Balance")
    parser.add_argument("--sims", type=int, default=1000, help="Number of simulations")
    
    args = parser.parse_args()
    
    logger.info("Generating Dummy Data (Strategy not connected yet)...")
    trades = simulate_dummy_data()
    
    stats = run_monte_carlo(trades, args.balance, args.sims)
    
    print("\n" + "="*40)
    print("MONTE CARLO RESULTS")
    print("="*40)
    print(f"Start Balance:      ${args.balance:,.2f}")
    print(f"Median Final Eq:    ${stats['median_equity']:,.2f}")
    print(f"Worst Case (5%):    ${stats['worst_case_equity']:,.2f}")
    print("-" * 40)
    print(f"Median Max DD:      {stats['median_max_dd']:.2f}%")
    print(f"Worst Max DD (5%):  {stats['worst_case_max_dd']:.2f}%")
    print(f"Risk of Ruin:       {stats['ruin_probability']:.2f}%")
    print("="*40 + "\n")
    
    if stats['ruin_probability'] > 1.0:
        logger.error(" STRATEGY FAILED: Risk of Ruin > 1%")
    else:
        logger.success("STRATEGY PASSED: Risk of Ruin acceptable.")

if __name__ == "__main__":
    main()
