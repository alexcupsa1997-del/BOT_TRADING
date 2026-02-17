"""
Walk-Forward Validator — Time-Series Cross-Validation with Purge + Embargo

Generates train/test folds for financial time series where:
- Folds are strictly chronological (no future leakage)
- A purge gap removes N days between train and test
- An embargo removes the last M% of training data
- Overfitting ratio is computed per configuration

Ref: FUSION_PLAN Fase 2, item 2.3
Inspired by: freqtrade DataKitchen + Marcos Lopez de Prado
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any
from loguru import logger


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Fold:
    """A single train/test fold."""
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_indices: np.ndarray      # Integer indices into original DataFrame
    test_indices: np.ndarray


@dataclass
class FoldResult:
    """Metrics from a single fold evaluation."""
    fold_id: int
    train_sharpe: float = 0.0
    test_sharpe: float = 0.0
    train_return: float = 0.0
    test_return: float = 0.0
    train_win_rate: float = 0.0
    test_win_rate: float = 0.0
    train_trades: int = 0
    test_trades: int = 0
    train_max_dd: float = 0.0
    test_max_dd: float = 0.0


@dataclass
class WalkForwardReport:
    """Aggregated walk-forward results."""
    fold_results: List[FoldResult]
    mean_test_sharpe: float = 0.0
    std_test_sharpe: float = 0.0
    min_test_sharpe: float = 0.0
    max_test_sharpe: float = 0.0
    mean_test_return: float = 0.0
    overfitting_ratio: float = 0.0  # mean(test_sharpe) / mean(train_sharpe)
    total_folds: int = 0
    degradation_pct: float = 0.0    # % of folds where test < train


# =============================================================================
# WALK-FORWARD VALIDATOR
# =============================================================================

class WalkForwardValidator:
    """
    Walk-forward cross-validation for financial ML.

    Configuration defaults:
        train_days = 60       # 2 months of training
        test_days  = 20       # 20 days of testing
        purge_days = 2        # 2-day gap between train and test
        embargo_pct = 0.01    # Remove last 1% of train set
        min_train_samples = 500

    For 2 years of data (730 days):
        Folds ~ (730 - 60) / 20 = ~33 folds

    Overfitting ratio:
        < 0.5 = strong overfitting
        > 0.8 = good generalization
    """

    def __init__(
        self,
        train_days: int = 60,
        test_days: int = 20,
        purge_days: int = 2,
        embargo_pct: float = 0.01,
        min_train_samples: int = 500,
        step_days: Optional[int] = None,
    ):
        self.train_days = train_days
        self.test_days = test_days
        self.purge_days = purge_days
        self.embargo_pct = embargo_pct
        self.min_train_samples = min_train_samples
        # Step size defaults to test_days (non-overlapping test sets)
        self.step_days = step_days or test_days

    def generate_folds(self, data: pd.DataFrame) -> List[Fold]:
        """
        Generate walk-forward folds from a DatetimeIndex DataFrame.

        Args:
            data: DataFrame with DatetimeIndex (sorted chronologically)

        Returns:
            List of Fold objects with train/test splits
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have a DatetimeIndex")

        index = data.index
        total_start = index[0]
        total_end = index[-1]

        folds: List[Fold] = []
        fold_id = 0
        train_start = total_start

        while True:
            train_end = train_start + pd.Timedelta(days=self.train_days)
            purge_end = train_end + pd.Timedelta(days=self.purge_days)
            test_start = purge_end
            test_end = test_start + pd.Timedelta(days=self.test_days)

            # Stop if test extends beyond data
            if test_end > total_end:
                break

            # Get train indices
            train_mask = (index >= train_start) & (index < train_end)

            # Apply embargo: remove last embargo_pct of train
            train_idx_all = np.where(train_mask)[0]
            if len(train_idx_all) < self.min_train_samples:
                train_start += pd.Timedelta(days=self.step_days)
                continue

            embargo_count = max(1, int(len(train_idx_all) * self.embargo_pct))
            train_indices = train_idx_all[:-embargo_count]

            if len(train_indices) < self.min_train_samples:
                train_start += pd.Timedelta(days=self.step_days)
                continue

            # Get test indices (after purge gap)
            test_mask = (index >= test_start) & (index < test_end)
            test_indices = np.where(test_mask)[0]

            if len(test_indices) == 0:
                train_start += pd.Timedelta(days=self.step_days)
                continue

            # Verify no overlap
            if len(train_indices) > 0 and len(test_indices) > 0:
                assert train_indices[-1] < test_indices[0], (
                    f"Overlap detected: train ends at {train_indices[-1]}, "
                    f"test starts at {test_indices[0]}"
                )

            actual_train_end = index[train_indices[-1]]
            actual_test_start = index[test_indices[0]]
            actual_test_end = index[test_indices[-1]]

            folds.append(Fold(
                fold_id=fold_id,
                train_start=train_start,
                train_end=actual_train_end,
                test_start=actual_test_start,
                test_end=actual_test_end,
                train_indices=train_indices,
                test_indices=test_indices,
            ))

            fold_id += 1
            train_start += pd.Timedelta(days=self.step_days)

        logger.info(f"Generated {len(folds)} walk-forward folds")
        return folds

    def evaluate(
        self,
        data: pd.DataFrame,
        train_fn: Callable[[pd.DataFrame], Any],
        test_fn: Callable[[Any, pd.DataFrame], FoldResult],
        folds: Optional[List[Fold]] = None,
    ) -> WalkForwardReport:
        """
        Run walk-forward evaluation.

        Args:
            data: Full dataset
            train_fn: Function(train_data) -> model
                      Trains a model on the training split
            test_fn: Function(model, test_data) -> FoldResult
                     Evaluates the model on the test split
            folds: Pre-generated folds (will generate if None)

        Returns:
            WalkForwardReport with per-fold and aggregated metrics
        """
        if folds is None:
            folds = self.generate_folds(data)

        if len(folds) == 0:
            logger.warning("No folds generated — insufficient data")
            return WalkForwardReport(fold_results=[], total_folds=0)

        fold_results: List[FoldResult] = []

        for fold in folds:
            logger.info(
                f"Fold {fold.fold_id}: train [{fold.train_start.date()} → "
                f"{fold.train_end.date()}] ({len(fold.train_indices)} samples), "
                f"test [{fold.test_start.date()} → {fold.test_end.date()}] "
                f"({len(fold.test_indices)} samples)"
            )

            train_data = data.iloc[fold.train_indices]
            test_data = data.iloc[fold.test_indices]

            # Train
            model = train_fn(train_data)

            # Test
            result = test_fn(model, test_data)
            result.fold_id = fold.fold_id
            fold_results.append(result)

        return self._aggregate(fold_results)

    def _aggregate(self, fold_results: List[FoldResult]) -> WalkForwardReport:
        """Aggregate fold results into a report."""
        if not fold_results:
            return WalkForwardReport(fold_results=[], total_folds=0)

        test_sharpes = [r.test_sharpe for r in fold_results]
        train_sharpes = [r.train_sharpe for r in fold_results]
        test_returns = [r.test_return for r in fold_results]

        mean_train = float(np.mean(train_sharpes)) if train_sharpes else 0.0
        mean_test = float(np.mean(test_sharpes))

        degraded = sum(
            1 for r in fold_results if r.test_sharpe < r.train_sharpe
        )

        report = WalkForwardReport(
            fold_results=fold_results,
            mean_test_sharpe=mean_test,
            std_test_sharpe=float(np.std(test_sharpes, ddof=1)) if len(test_sharpes) > 1 else 0.0,
            min_test_sharpe=float(np.min(test_sharpes)),
            max_test_sharpe=float(np.max(test_sharpes)),
            mean_test_return=float(np.mean(test_returns)),
            overfitting_ratio=mean_test / mean_train if mean_train != 0 else 0.0,
            total_folds=len(fold_results),
            degradation_pct=degraded / len(fold_results) if fold_results else 0.0,
        )

        logger.info(
            f"Walk-Forward: {report.total_folds} folds | "
            f"Mean test Sharpe: {report.mean_test_sharpe:.3f} +/- {report.std_test_sharpe:.3f} | "
            f"Overfitting ratio: {report.overfitting_ratio:.2f}"
        )

        return report

    @staticmethod
    def format_report(report: WalkForwardReport) -> str:
        """Format walk-forward report as human-readable text."""
        lines = [
            "=" * 60,
            "         WALK-FORWARD VALIDATION REPORT",
            "=" * 60,
            f"  Total Folds:            {report.total_folds}",
            f"  Mean Test Sharpe:       {report.mean_test_sharpe:.3f}",
            f"  Std Test Sharpe:        {report.std_test_sharpe:.3f}",
            f"  Min Test Sharpe:        {report.min_test_sharpe:.3f}",
            f"  Max Test Sharpe:        {report.max_test_sharpe:.3f}",
            f"  Mean Test Return:       {report.mean_test_return:.4f}",
            "-" * 60,
            f"  Overfitting Ratio:      {report.overfitting_ratio:.3f}",
        ]

        if report.overfitting_ratio < 0.5:
            lines.append("  Assessment:             STRONG OVERFITTING")
        elif report.overfitting_ratio < 0.8:
            lines.append("  Assessment:             MODERATE OVERFITTING")
        else:
            lines.append("  Assessment:             GOOD GENERALIZATION")

        lines.append(f"  Degradation:            {report.degradation_pct:.1%} of folds")
        lines.append("-" * 60)

        # Per-fold summary
        lines.append("  Fold | Train Sharpe | Test Sharpe | Test Return | Trades")
        lines.append("  " + "-" * 56)
        for r in report.fold_results:
            lines.append(
                f"  {r.fold_id:4d} | {r.train_sharpe:11.3f} | "
                f"{r.test_sharpe:10.3f} | {r.test_return:10.4f} | {r.test_trades:6d}"
            )

        lines.append("=" * 60)
        return "\n".join(lines)


__all__ = [
    "Fold",
    "FoldResult",
    "WalkForwardReport",
    "WalkForwardValidator",
]
