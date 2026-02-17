"""
Monte Carlo Simulator — Risk assessment post-backtest.

Shuffles trade order across N simulations to compute probabilistic
risk metrics: risk of ruin, confidence intervals, drawdown distribution.

Input: List[Trade] from BacktestEngine results
Output: probability distributions of future performance

Ref: FUSION_PLAN Fase 5, item 5.1
     Stock-Prediction-Models simulation notebooks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from loguru import logger


@dataclass
class MonteCarloConfig:
    """Configuration for MonteCarloSimulator."""
    n_simulations: int = 10_000
    confidence_level: float = 0.95
    seed: int = 42


@dataclass
class MonteCarloResult:
    """Complete Monte Carlo simulation result."""
    risk_of_ruin: float
    confidence_interval: Tuple[float, float]
    drawdown_dist: Dict[str, float]
    return_dist: Dict[str, float]
    n_simulations: int
    n_trades: int


class MonteCarloSimulator:
    """
    Monte Carlo simulation for post-backtest risk assessment.

    For each simulation, the trade order is shuffled (bootstrap),
    the equity curve is recomputed, and risk metrics are extracted.
    This answers: "How likely is my strategy to blow up?"

    Usage:
        mc = MonteCarloSimulator(trades=result.journal)
        ror = mc.risk_of_ruin(max_drawdown_pct=0.30)
        ci = mc.confidence_interval(0.95)
        dd = mc.drawdown_distribution()
    """

    def __init__(self, trades, n_simulations: int = 10_000, seed: int = 42):
        """
        Args:
            trades: List of Trade objects (or any object with `pnl_pct` attr),
                    or a list of float returns.
            n_simulations: Number of bootstrap simulations.
            seed: Random seed for reproducibility.
        """
        if not trades:
            raise ValueError("Cannot run Monte Carlo with empty trade list")

        if hasattr(trades[0], "pnl_pct"):
            self.returns = np.array([float(t.pnl_pct) for t in trades])
        else:
            self.returns = np.array([float(r) for r in trades])

        self.n_simulations = n_simulations
        self.seed = seed
        self._rng = np.random.default_rng(seed)
        self._equity_curves: np.ndarray | None = None

    @property
    def n_trades(self) -> int:
        return len(self.returns)

    def run_simulations(self) -> np.ndarray:
        """
        Run all simulations and cache equity curves.

        Returns:
            Array of shape (n_simulations, n_trades + 1) with equity
            curves starting at 1.0.
        """
        if self._equity_curves is not None:
            return self._equity_curves

        n = self.n_trades
        curves = np.ones((self.n_simulations, n + 1))

        for i in range(self.n_simulations):
            shuffled = self._rng.permutation(self.returns)
            curves[i, 1:] = np.cumprod(1 + shuffled)

        self._equity_curves = curves
        logger.info(f"Monte Carlo: {self.n_simulations} simulations on "
                    f"{n} trades completed")
        return curves

    def risk_of_ruin(self, max_drawdown_pct: float = 0.30) -> float:
        """
        Probability that max drawdown exceeds threshold.

        Args:
            max_drawdown_pct: Drawdown threshold (e.g. 0.30 = 30%).

        Returns:
            Probability [0, 1]. If > 0.05, strategy is risky.
        """
        curves = self.run_simulations()
        ruin_count = 0

        for i in range(self.n_simulations):
            equity = curves[i]
            running_max = np.maximum.accumulate(equity)
            drawdowns = (running_max - equity) / np.maximum(running_max, 1e-10)
            if np.max(drawdowns) >= max_drawdown_pct:
                ruin_count += 1

        ror = ruin_count / self.n_simulations
        return ror

    def confidence_interval(self, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Confidence interval on final equity.

        Args:
            confidence: Confidence level (e.g. 0.95 for 95% CI).

        Returns:
            (lower_bound, upper_bound) of final equity (starting from 1.0).
        """
        curves = self.run_simulations()
        final_equity = curves[:, -1]

        alpha = (1 - confidence) / 2
        lower = float(np.percentile(final_equity, alpha * 100))
        upper = float(np.percentile(final_equity, (1 - alpha) * 100))

        return (lower, upper)

    def drawdown_distribution(self) -> Dict[str, float]:
        """
        Distribution of max drawdowns across all simulations.

        Returns:
            Dict with mean_dd, median_dd, p95_dd, p99_dd, max_dd.
        """
        curves = self.run_simulations()
        max_dds = np.zeros(self.n_simulations)

        for i in range(self.n_simulations):
            equity = curves[i]
            running_max = np.maximum.accumulate(equity)
            drawdowns = (running_max - equity) / np.maximum(running_max, 1e-10)
            max_dds[i] = np.max(drawdowns)

        return {
            "mean_dd": float(np.mean(max_dds)),
            "median_dd": float(np.median(max_dds)),
            "p95_dd": float(np.percentile(max_dds, 95)),
            "p99_dd": float(np.percentile(max_dds, 99)),
            "max_dd": float(np.max(max_dds)),
        }

    def expected_return_distribution(self, horizon_trades: int = 0) -> Dict[str, float]:
        """
        Distribution of returns across all simulations.

        Args:
            horizon_trades: Number of trades to project (0 = use all trades).

        Returns:
            Dict with mean_return, median_return, p5_return, p95_return,
            prob_profitable.
        """
        curves = self.run_simulations()

        if horizon_trades > 0 and horizon_trades < self.n_trades:
            final_equity = curves[:, horizon_trades]
        else:
            final_equity = curves[:, -1]

        total_returns = final_equity - 1.0  # relative to starting equity of 1.0

        return {
            "mean_return": float(np.mean(total_returns)),
            "median_return": float(np.median(total_returns)),
            "p5_return": float(np.percentile(total_returns, 5)),
            "p95_return": float(np.percentile(total_returns, 95)),
            "prob_profitable": float(np.mean(total_returns > 0)),
        }

    def full_report(self, max_drawdown_pct: float = 0.30,
                    confidence: float = 0.95) -> MonteCarloResult:
        """Run all analyses and return a complete result."""
        return MonteCarloResult(
            risk_of_ruin=self.risk_of_ruin(max_drawdown_pct),
            confidence_interval=self.confidence_interval(confidence),
            drawdown_dist=self.drawdown_distribution(),
            return_dist=self.expected_return_distribution(),
            n_simulations=self.n_simulations,
            n_trades=self.n_trades,
        )

    def format_report(self, max_drawdown_pct: float = 0.30,
                      confidence: float = 0.95) -> str:
        """Human-readable Monte Carlo report."""
        result = self.full_report(max_drawdown_pct, confidence)
        ci = result.confidence_interval
        dd = result.drawdown_dist
        rd = result.return_dist

        lines = [
            "=" * 55,
            "        MONTE CARLO RISK ASSESSMENT",
            "=" * 55,
            f"  Simulations:        {result.n_simulations:,}",
            f"  Trades analyzed:    {result.n_trades}",
            "",
            f"  Risk of Ruin ({max_drawdown_pct:.0%} DD): {result.risk_of_ruin:.2%}",
            f"  {'SAFE' if result.risk_of_ruin < 0.05 else 'RISKY'}",
            "",
            f"  {confidence:.0%} Confidence Interval:",
            f"    Equity: [{ci[0]:.4f}, {ci[1]:.4f}]",
            f"    (starting from 1.0)",
            "",
            "  Drawdown Distribution:",
            f"    Mean:   {dd['mean_dd']:.2%}",
            f"    Median: {dd['median_dd']:.2%}",
            f"    P95:    {dd['p95_dd']:.2%}",
            f"    P99:    {dd['p99_dd']:.2%}",
            f"    Worst:  {dd['max_dd']:.2%}",
            "",
            "  Expected Return Distribution:",
            f"    Mean:   {rd['mean_return']:+.2%}",
            f"    Median: {rd['median_return']:+.2%}",
            f"    P5:     {rd['p5_return']:+.2%}  (pessimistic)",
            f"    P95:    {rd['p95_return']:+.2%}  (optimistic)",
            f"    P(profit): {rd['prob_profitable']:.1%}",
            "=" * 55,
        ]
        return "\n".join(lines)
