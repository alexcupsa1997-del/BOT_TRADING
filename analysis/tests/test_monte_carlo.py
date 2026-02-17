"""Tests for MonteCarloSimulator (Fase 5)."""

import numpy as np
import pytest

from src.quant.monte_carlo import (
    MonteCarloSimulator, MonteCarloConfig, MonteCarloResult,
)


def _make_trades(n: int = 100, win_rate: float = 0.55,
                 avg_win: float = 0.02, avg_loss: float = -0.015,
                 seed: int = 42) -> list:
    """Generate synthetic trade returns."""
    rng = np.random.default_rng(seed)
    trades = []
    for _ in range(n):
        if rng.random() < win_rate:
            trades.append(rng.normal(avg_win, 0.005))
        else:
            trades.append(rng.normal(avg_loss, 0.005))
    return trades


class TestMonteCarloBasic:
    def test_risk_of_ruin_bounded(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        ror = mc.risk_of_ruin(0.30)
        assert 0.0 <= ror <= 1.0

    def test_risk_of_ruin_all_winners(self):
        winners = [0.02] * 50
        mc = MonteCarloSimulator(winners, n_simulations=500, seed=42)
        ror = mc.risk_of_ruin(0.30)
        assert ror < 0.01  # all winners → negligible ruin

    def test_risk_of_ruin_all_losers(self):
        losers = [-0.05] * 50
        mc = MonteCarloSimulator(losers, n_simulations=500, seed=42)
        ror = mc.risk_of_ruin(0.10)
        assert ror > 0.90  # all losers → almost certain ruin

    def test_confidence_interval_contains_mean(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=1000, seed=42)
        ci = mc.confidence_interval(0.95)
        curves = mc.run_simulations()
        mean_final = float(np.mean(curves[:, -1]))
        assert ci[0] <= mean_final <= ci[1]

    def test_confidence_interval_ordering(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        ci = mc.confidence_interval(0.95)
        assert ci[0] < ci[1]

    def test_drawdown_distribution_keys(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        dd = mc.drawdown_distribution()
        expected_keys = {"mean_dd", "median_dd", "p95_dd", "p99_dd", "max_dd"}
        assert set(dd.keys()) == expected_keys

    def test_drawdown_values_bounded(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        dd = mc.drawdown_distribution()
        for v in dd.values():
            assert 0.0 <= v <= 1.0

    def test_drawdown_ordering(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        dd = mc.drawdown_distribution()
        assert dd["mean_dd"] <= dd["p95_dd"] <= dd["max_dd"]

    def test_expected_return_distribution(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        rd = mc.expected_return_distribution()
        expected_keys = {"mean_return", "median_return", "p5_return",
                         "p95_return", "prob_profitable"}
        assert set(rd.keys()) == expected_keys
        assert 0.0 <= rd["prob_profitable"] <= 1.0

    def test_expected_return_with_horizon(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        rd_all = mc.expected_return_distribution(horizon_trades=0)
        rd_50 = mc.expected_return_distribution(horizon_trades=50)
        # Shorter horizon → smaller absolute returns (generally)
        assert rd_50 is not None  # just check it runs

    def test_empty_trades_raises(self):
        with pytest.raises(ValueError, match="empty"):
            MonteCarloSimulator([], n_simulations=100)

    def test_reproducibility(self):
        trades = _make_trades()
        mc1 = MonteCarloSimulator(trades, n_simulations=500, seed=42)
        mc2 = MonteCarloSimulator(trades, n_simulations=500, seed=42)
        ror1 = mc1.risk_of_ruin(0.25)
        ror2 = mc2.risk_of_ruin(0.25)
        assert ror1 == ror2

    def test_different_seeds_differ(self):
        trades = _make_trades()
        mc1 = MonteCarloSimulator(trades, n_simulations=1000, seed=42)
        mc2 = MonteCarloSimulator(trades, n_simulations=1000, seed=99)
        ci1 = mc1.confidence_interval(0.95)
        ci2 = mc2.confidence_interval(0.95)
        # Very unlikely to be exactly equal with different seeds
        assert ci1 != ci2


class TestMonteCarloFullReport:
    def test_full_report_returns_dataclass(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        result = mc.full_report()
        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 500
        assert result.n_trades == 100

    def test_format_report_returns_string(self):
        mc = MonteCarloSimulator(_make_trades(), n_simulations=500, seed=42)
        report = mc.format_report()
        assert isinstance(report, str)
        assert "MONTE CARLO" in report
        assert "Risk of Ruin" in report
        assert "Drawdown" in report


class TestMonteCarloWithObjects:
    def test_accepts_objects_with_pnl_pct(self):
        """Simulate Trade objects with pnl_pct attribute."""
        class FakeTrade:
            def __init__(self, pnl_pct):
                self.pnl_pct = pnl_pct

        trades = [FakeTrade(0.02), FakeTrade(-0.01), FakeTrade(0.03)]
        mc = MonteCarloSimulator(trades, n_simulations=100, seed=42)
        assert mc.n_trades == 3
        ror = mc.risk_of_ruin(0.30)
        assert 0.0 <= ror <= 1.0


class TestMonteCarloConfig:
    def test_defaults(self):
        cfg = MonteCarloConfig()
        assert cfg.n_simulations == 10_000
        assert cfg.confidence_level == 0.95
        assert cfg.seed == 42

    def test_caching(self):
        mc = MonteCarloSimulator(_make_trades(50), n_simulations=200, seed=42)
        curves1 = mc.run_simulations()
        curves2 = mc.run_simulations()
        assert curves1 is curves2  # same object — cached
