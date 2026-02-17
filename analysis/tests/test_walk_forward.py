"""
Tests for WalkForwardValidator — Purge + Embargo validation

Ref: FUSION_PLAN Fase 2, item 2.6
"""

import numpy as np
import pandas as pd
import pytest

from src.ml.training.walk_forward import (
    WalkForwardValidator,
    Fold,
    FoldResult,
    WalkForwardReport,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def two_year_data():
    """730 days of hourly data (17520 rows)."""
    np.random.seed(42)
    n = 730 * 24  # 2 years hourly
    dates = pd.date_range("2023-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(np.random.normal(0, 0.1, n))
    return pd.DataFrame(
        {
            "open": close + np.random.normal(0, 0.05, n),
            "high": close + np.abs(np.random.normal(0.1, 0.05, n)),
            "low": close - np.abs(np.random.normal(0.1, 0.05, n)),
            "close": close,
            "volume": np.random.randint(100, 1000, n).astype(float),
        },
        index=dates,
    )


@pytest.fixture
def short_data():
    """30 days of hourly data — too short for default params."""
    np.random.seed(42)
    n = 30 * 24
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(np.random.normal(0, 0.1, n))
    return pd.DataFrame({"close": close}, index=dates)


@pytest.fixture
def daily_data():
    """500 days of daily data."""
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2023-06-01", periods=n, freq="1D")
    close = 100 + np.cumsum(np.random.normal(0.01, 0.5, n))
    return pd.DataFrame(
        {
            "open": close + np.random.normal(0, 0.1, n),
            "high": close + np.abs(np.random.normal(0.2, 0.1, n)),
            "low": close - np.abs(np.random.normal(0.2, 0.1, n)),
            "close": close,
        },
        index=dates,
    )


# =============================================================================
# FOLD GENERATION TESTS
# =============================================================================

class TestFoldGeneration:
    def test_generates_folds(self, two_year_data):
        wf = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        folds = wf.generate_folds(two_year_data)
        assert len(folds) > 0

    def test_fold_count_approximately_correct(self, two_year_data):
        wf = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        folds = wf.generate_folds(two_year_data)
        # Expected: ~33 folds for 2 years
        assert 20 <= len(folds) <= 40

    def test_no_overlap_between_train_and_test(self, two_year_data):
        wf = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        folds = wf.generate_folds(two_year_data)
        for fold in folds:
            assert fold.train_indices[-1] < fold.test_indices[0], (
                f"Overlap in fold {fold.fold_id}: "
                f"train ends at {fold.train_indices[-1]}, "
                f"test starts at {fold.test_indices[0]}"
            )

    def test_purge_gap_exists(self, two_year_data):
        wf = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        folds = wf.generate_folds(two_year_data)
        for fold in folds:
            train_end_time = two_year_data.index[fold.train_indices[-1]]
            test_start_time = two_year_data.index[fold.test_indices[0]]
            gap = (test_start_time - train_end_time).total_seconds() / 86400
            # Gap should be at least purge_days (roughly, accounting for embargo)
            assert gap >= 1.0, f"Fold {fold.fold_id}: gap is only {gap:.1f} days"

    def test_embargo_reduces_train_set(self, two_year_data):
        wf_no_embargo = WalkForwardValidator(
            train_days=60, test_days=20, purge_days=2, embargo_pct=0.0,
            min_train_samples=1,
        )
        wf_embargo = WalkForwardValidator(
            train_days=60, test_days=20, purge_days=2, embargo_pct=0.05,
            min_train_samples=1,
        )
        folds_no = wf_no_embargo.generate_folds(two_year_data)
        folds_yes = wf_embargo.generate_folds(two_year_data)
        if folds_no and folds_yes:
            # With embargo, train set should be smaller
            assert len(folds_yes[0].train_indices) < len(folds_no[0].train_indices)

    def test_chronological_order(self, two_year_data):
        wf = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        folds = wf.generate_folds(two_year_data)
        for i in range(1, len(folds)):
            assert folds[i].train_start >= folds[i - 1].train_start

    def test_insufficient_data_returns_empty(self, short_data):
        wf = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        folds = wf.generate_folds(short_data)
        assert len(folds) == 0

    def test_requires_datetime_index(self):
        bad = pd.DataFrame({"close": [1, 2, 3]})
        wf = WalkForwardValidator()
        with pytest.raises(ValueError, match="DatetimeIndex"):
            wf.generate_folds(bad)


# =============================================================================
# CUSTOM STEP SIZE TESTS
# =============================================================================

class TestStepSize:
    def test_custom_step_produces_more_folds(self, two_year_data):
        wf_default = WalkForwardValidator(train_days=60, test_days=20, purge_days=2)
        wf_small_step = WalkForwardValidator(
            train_days=60, test_days=20, purge_days=2, step_days=10,
        )
        folds_default = wf_default.generate_folds(two_year_data)
        folds_small = wf_small_step.generate_folds(two_year_data)
        assert len(folds_small) > len(folds_default)


# =============================================================================
# EVALUATION TESTS
# =============================================================================

class TestEvaluation:
    def test_evaluate_with_mock_functions(self, daily_data):
        wf = WalkForwardValidator(
            train_days=60, test_days=20, purge_days=2, min_train_samples=10,
        )

        def mock_train(train_data):
            return {"mean_close": train_data["close"].mean()}

        def mock_test(model, test_data):
            return FoldResult(
                fold_id=0,
                train_sharpe=1.0,
                test_sharpe=0.8,
                train_return=0.05,
                test_return=0.03,
                test_trades=10,
            )

        report = wf.evaluate(daily_data, mock_train, mock_test)
        assert isinstance(report, WalkForwardReport)
        assert report.total_folds > 0
        assert report.overfitting_ratio > 0

    def test_overfitting_ratio_computed(self, daily_data):
        wf = WalkForwardValidator(
            train_days=60, test_days=20, purge_days=2, min_train_samples=10,
        )

        def train_fn(d):
            return None

        def test_fn(m, d):
            return FoldResult(
                fold_id=0, train_sharpe=2.0, test_sharpe=1.0,
            )

        report = wf.evaluate(daily_data, train_fn, test_fn)
        # overfitting_ratio = mean_test / mean_train = 1.0 / 2.0 = 0.5
        assert abs(report.overfitting_ratio - 0.5) < 0.01


# =============================================================================
# REPORT FORMATTING TESTS
# =============================================================================

class TestReportFormatting:
    def test_format_report(self):
        report = WalkForwardReport(
            fold_results=[
                FoldResult(fold_id=0, train_sharpe=1.5, test_sharpe=1.0, test_return=0.03, test_trades=5),
                FoldResult(fold_id=1, train_sharpe=1.8, test_sharpe=0.9, test_return=0.02, test_trades=3),
            ],
            mean_test_sharpe=0.95,
            std_test_sharpe=0.07,
            min_test_sharpe=0.9,
            max_test_sharpe=1.0,
            mean_test_return=0.025,
            overfitting_ratio=0.58,
            total_folds=2,
            degradation_pct=1.0,
        )
        text = WalkForwardValidator.format_report(report)
        assert "WALK-FORWARD VALIDATION REPORT" in text
        assert "Overfitting Ratio" in text
        assert "MODERATE OVERFITTING" in text

    def test_good_generalization_label(self):
        report = WalkForwardReport(
            fold_results=[],
            overfitting_ratio=0.9,
            total_folds=0,
        )
        text = WalkForwardValidator.format_report(report)
        assert "GOOD GENERALIZATION" in text

    def test_strong_overfitting_label(self):
        report = WalkForwardReport(
            fold_results=[],
            overfitting_ratio=0.3,
            total_folds=0,
        )
        text = WalkForwardValidator.format_report(report)
        assert "STRONG OVERFITTING" in text
