"""
Tests for TripleBarrier — Labeling + Exit Management

Ref: FUSION_PLAN Fase 2, item 2.7
"""

import numpy as np
import pandas as pd
import pytest
from decimal import Decimal

from src.quant.triple_barrier import (
    TripleBarrier,
    BarrierState,
    ExitSignal,
    ExitReason,
    BarrierConfig,
)


# =============================================================================
# FIXTURES — Synthetic market data
# =============================================================================

@pytest.fixture
def trending_up_data():
    """Synthetic uptrend: close goes from 100 to ~130."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(np.random.normal(0.05, 0.3, n))
    high = close + np.abs(np.random.normal(0.2, 0.1, n))
    low = close - np.abs(np.random.normal(0.2, 0.1, n))
    open_ = close + np.random.normal(0, 0.1, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=dates,
    )


@pytest.fixture
def trending_down_data():
    """Synthetic downtrend: close goes from 100 to ~70."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = 100 - np.cumsum(np.abs(np.random.normal(0.05, 0.3, n)))
    high = close + np.abs(np.random.normal(0.2, 0.1, n))
    low = close - np.abs(np.random.normal(0.2, 0.1, n))
    open_ = close + np.random.normal(0, 0.1, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=dates,
    )


@pytest.fixture
def flat_data():
    """Synthetic flat market: close oscillates around 100."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    close = 100 + np.random.normal(0, 0.5, n).cumsum() * 0.01
    high = close + 0.1
    low = close - 0.1
    open_ = close
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=dates,
    )


# =============================================================================
# LABELING TESTS
# =============================================================================

class TestTripleBarrierLabeling:
    def test_labels_are_valid(self, trending_up_data):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        labels = tb.label_series(trending_up_data, side=1)
        valid = labels.dropna()
        assert set(valid.unique()).issubset({-1, 0, 1})

    def test_uptrend_has_more_wins(self, trending_up_data):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        labels = tb.label_series(trending_up_data, side=1)
        valid = labels.dropna()
        wins = (valid == 1).sum()
        losses = (valid == -1).sum()
        # In uptrend with long bias, wins should dominate
        assert wins > losses

    def test_downtrend_short_has_more_wins(self, trending_down_data):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        labels = tb.label_series(trending_down_data, side=-1)
        valid = labels.dropna()
        wins = (valid == 1).sum()
        losses = (valid == -1).sum()
        assert wins > losses

    def test_sl_priority_over_tp(self):
        """If SL and TP both hit on same bar, SL wins (safety first)."""
        dates = pd.date_range("2025-01-01", periods=5, freq="1h")
        # Bar 0: entry at 100. Bar 1: low=96, high=104 (both barriers)
        df = pd.DataFrame({
            "open": [100, 99, 100, 100, 100],
            "high": [101, 104, 101, 101, 101],
            "low": [99, 96, 99, 99, 99],
            "close": [100, 100, 100, 100, 100],
        }, index=dates)
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        labels = tb.label_series(df, side=1)
        # SL at 98, TP at 103. Bar 1 low=96 < 98 → SL hit
        assert labels.iloc[0] == -1

    def test_detailed_returns_barrier_info(self, trending_up_data):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        detail = tb.label_series_detailed(trending_up_data, side=1)
        assert "label" in detail.columns
        assert "barrier_type" in detail.columns
        assert "first_touch_bar" in detail.columns
        assert "return_pct" in detail.columns

    def test_timeout_labels(self, flat_data):
        """Flat market with tight barriers should produce timeouts."""
        tb = TripleBarrier(sl_pct=0.5, tp_pct=0.5, max_bars=5)
        labels = tb.label_series(flat_data, side=1)
        valid = labels.dropna()
        timeouts = (valid == 0).sum()
        assert timeouts > 0

    def test_reproducibility(self, trending_up_data):
        """Same data + same config = same labels."""
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
        labels1 = tb.label_series(trending_up_data, side=1)
        labels2 = tb.label_series(trending_up_data, side=1)
        pd.testing.assert_series_equal(labels1, labels2)


# =============================================================================
# EXIT MANAGEMENT TESTS
# =============================================================================

class TestTripleBarrierExitManagement:
    def test_sl_triggers_long(self):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)
        # SL at 98. Bar with low=97 triggers SL
        sig = tb.check_exit(
            state,
            bar_open=Decimal("99"), bar_high=Decimal("100"),
            bar_low=Decimal("97"), bar_close=Decimal("98"),
            bar_idx=1,
        )
        assert sig is not None
        assert sig.reason == ExitReason.STOP_LOSS
        assert sig.pnl_pct < 0

    def test_tp_triggers_long(self):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)
        # TP at 103. Bar with high=104 triggers TP
        sig = tb.check_exit(
            state,
            bar_open=Decimal("102"), bar_high=Decimal("104"),
            bar_low=Decimal("101"), bar_close=Decimal("103"),
            bar_idx=1,
        )
        assert sig is not None
        assert sig.reason == ExitReason.TAKE_PROFIT
        assert sig.pnl_pct > 0

    def test_sl_triggers_short(self):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=-1, bar_idx=0)
        # Short SL at 102. Bar with high=103 triggers SL
        sig = tb.check_exit(
            state,
            bar_open=Decimal("101"), bar_high=Decimal("103"),
            bar_low=Decimal("100"), bar_close=Decimal("102"),
            bar_idx=1,
        )
        assert sig is not None
        assert sig.reason == ExitReason.STOP_LOSS

    def test_tp_triggers_short(self):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=-1, bar_idx=0)
        # Short TP at 97. Bar with low=96 triggers TP
        sig = tb.check_exit(
            state,
            bar_open=Decimal("98"), bar_high=Decimal("99"),
            bar_low=Decimal("96"), bar_close=Decimal("97"),
            bar_idx=1,
        )
        assert sig is not None
        assert sig.reason == ExitReason.TAKE_PROFIT

    def test_time_limit(self):
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=5)
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)
        # No SL/TP hit for 5 bars, then time limit
        for i in range(1, 5):
            sig = tb.check_exit(
                state,
                bar_open=Decimal("100"), bar_high=Decimal("100.5"),
                bar_low=Decimal("99.5"), bar_close=Decimal("100"),
                bar_idx=i,
            )
            assert sig is None

        sig = tb.check_exit(
            state,
            bar_open=Decimal("100"), bar_high=Decimal("100.5"),
            bar_low=Decimal("99.5"), bar_close=Decimal("100.1"),
            bar_idx=5,
        )
        assert sig is not None
        assert sig.reason == ExitReason.TIME_LIMIT

    def test_trailing_stop_activates(self):
        tb = TripleBarrier(
            sl_pct=0.05, tp_pct=0.10, max_bars=100,
            trailing=True, trailing_activation=0.03, trailing_delta=0.01,
        )
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)

        # Move up to 104 (activates trailing at 103)
        # Low stays above trailing SL (104 * 0.99 = 102.96)
        sig = tb.check_exit(
            state,
            bar_open=Decimal("102"), bar_high=Decimal("104"),
            bar_low=Decimal("103"), bar_close=Decimal("103.5"),
            bar_idx=1,
        )
        assert sig is None
        assert state.trailing_active is True
        # Trailing SL should be 104 * (1 - 0.01) = 102.96
        assert state.trailing_sl == Decimal("104") * (1 - Decimal("0.01"))

        # Now drop below trailing SL (102.96)
        sig = tb.check_exit(
            state,
            bar_open=Decimal("103"), bar_high=Decimal("103.5"),
            bar_low=Decimal("102"), bar_close=Decimal("102.5"),
            bar_idx=2,
        )
        assert sig is not None
        assert sig.reason == ExitReason.TRAILING_STOP

    def test_no_exit_when_price_within_barriers(self):
        tb = TripleBarrier(sl_pct=0.05, tp_pct=0.05, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)
        sig = tb.check_exit(
            state,
            bar_open=Decimal("100"), bar_high=Decimal("101"),
            bar_low=Decimal("99"), bar_close=Decimal("100.5"),
            bar_idx=1,
        )
        assert sig is None

    def test_gap_down_fills_at_open(self):
        """If open is already past SL, fill at open (gap scenario)."""
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)
        # SL at 98. Bar opens at 96 (gap down past SL)
        sig = tb.check_exit(
            state,
            bar_open=Decimal("96"), bar_high=Decimal("97"),
            bar_low=Decimal("95"), bar_close=Decimal("96.5"),
            bar_idx=1,
        )
        assert sig is not None
        assert sig.reason == ExitReason.STOP_LOSS
        assert sig.exit_price == Decimal("96")  # Filled at open, not SL

    def test_decimal_prices(self):
        """All exit prices should be Decimal."""
        tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=100)
        state = tb.open_position(Decimal("100"), direction=1, bar_idx=0)
        sig = tb.check_exit(
            state,
            bar_open=Decimal("99"), bar_high=Decimal("100"),
            bar_low=Decimal("97"), bar_close=Decimal("98"),
            bar_idx=1,
        )
        assert isinstance(sig.exit_price, Decimal)
