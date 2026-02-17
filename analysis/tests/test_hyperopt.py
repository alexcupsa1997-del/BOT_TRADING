"""
Tests for HyperoptEngine — Bayesian hyperparameter optimization.

Ref: FUSION_PLAN Fase 3
"""

import numpy as np
import pytest

from src.ml.training.hyperopt_engine import (
    HyperoptEngine,
    HyperoptResult,
    SearchSpace,
)


class TestHyperoptEngine:
    def test_basic_optimization(self):
        """Optimize a simple quadratic function."""
        try:
            import optuna  # noqa
        except ImportError:
            pytest.skip("optuna not installed")

        engine = HyperoptEngine(n_trials=10, seed=42)
        engine.add_param("x", "float", low=-5.0, high=5.0)
        engine.add_param("y", "float", low=-5.0, high=5.0)

        def objective(trial, params):
            # Minimize (x-1)^2 + (y+2)^2
            return (params["x"] - 1) ** 2 + (params["y"] + 2) ** 2

        result = engine.optimize(objective)

        assert isinstance(result, HyperoptResult)
        assert result.n_trials == 10
        assert "x" in result.best_params
        assert "y" in result.best_params
        # Best should be somewhat close to (1, -2)
        assert result.best_score < 10.0  # At least better than random

    def test_returns_trial_history(self):
        try:
            import optuna  # noqa
        except ImportError:
            pytest.skip("optuna not installed")

        engine = HyperoptEngine(n_trials=5, seed=42)
        engine.add_param("x", "float", low=0.0, high=1.0)

        result = engine.optimize(lambda trial, params: params["x"] ** 2)

        assert len(result.trial_history) == 5
        assert "score" in result.trial_history.columns
        assert "x" in result.trial_history.columns

    def test_integer_and_categorical_params(self):
        try:
            import optuna  # noqa
        except ImportError:
            pytest.skip("optuna not installed")

        engine = HyperoptEngine(n_trials=5, seed=42)
        engine.add_param("layers", "int", low=1, high=4)
        engine.add_param("activation", "categorical", choices=["relu", "tanh"])

        def objective(trial, params):
            return params["layers"] * (1 if params["activation"] == "relu" else 2)

        result = engine.optimize(objective)
        assert "layers" in result.best_params
        assert result.best_params["activation"] in ["relu", "tanh"]

    def test_log_float_param(self):
        try:
            import optuna  # noqa
        except ImportError:
            pytest.skip("optuna not installed")

        engine = HyperoptEngine(n_trials=5, seed=42)
        engine.add_param("lr", "log_float", low=1e-5, high=1e-1)

        result = engine.optimize(lambda trial, params: params["lr"])
        assert 1e-5 <= result.best_params["lr"] <= 1e-1

    def test_add_model_space(self):
        engine = HyperoptEngine(n_trials=5, seed=42)
        engine.add_model_space("bilstm")
        assert len(engine._search_space) == 4  # hidden_dim, num_layers, dropout, lr

    def test_compute_loss_sharpe(self):
        metrics = {"sharpe_ratio": 1.5, "annual_return": 0.2, "max_drawdown": 0.1}
        loss = HyperoptEngine.compute_loss(metrics, "sharpe")
        assert loss == -1.5

    def test_compute_loss_return(self):
        metrics = {"annual_return": 0.3}
        loss = HyperoptEngine.compute_loss(metrics, "return")
        assert loss == -0.3

    def test_compute_loss_risk_adjusted(self):
        metrics = {"annual_return": 0.2, "max_drawdown": 0.1}
        loss = HyperoptEngine.compute_loss(metrics, "risk_adjusted")
        # -(0.2 - 2*0.1) = -(0.2 - 0.2) = 0.0
        assert abs(loss) < 0.01

    def test_different_samplers(self):
        try:
            import optuna  # noqa
        except ImportError:
            pytest.skip("optuna not installed")

        for sampler in ["tpe", "random"]:
            engine = HyperoptEngine(n_trials=3, sampler=sampler, seed=42)
            engine.add_param("x", "float", low=0.0, high=1.0)
            result = engine.optimize(lambda trial, params: params["x"])
            assert result.n_trials == 3
