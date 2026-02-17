"""
HyperoptEngine — Bayesian Hyperparameter Optimization with Optuna

Search space domains:
1. Model hyperparams (hidden_dim, layers, etc.)
2. Training hyperparams (lr, batch_size, dropout)
3. Strategy hyperparams (indicator params, thresholds)

Loss functions: sharpe, return, risk_adjusted.
Pruning: stop unpromising trials early.

Ref: FUSION_PLAN Fase 3, item 3.1
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Any, List
from loguru import logger


@dataclass
class HyperoptResult:
    """Result of hyperparameter optimization."""
    best_params: Dict[str, Any]
    best_score: float
    n_trials: int
    trial_history: pd.DataFrame  # All trials with params + scores


@dataclass
class SearchSpace:
    """Definition of a hyperparameter search space."""
    name: str
    param_type: str  # "int", "float", "categorical", "log_float"
    low: Any = None
    high: Any = None
    choices: List[Any] = field(default_factory=list)
    log: bool = False


class HyperoptEngine:
    """
    Bayesian hyperparameter optimization using Optuna.

    Usage:
        engine = HyperoptEngine(n_trials=100, loss_fn="sharpe")
        engine.add_param("lr", "log_float", low=1e-5, high=1e-2)
        engine.add_param("hidden_dim", "int", low=64, high=256)
        result = engine.optimize(objective_fn)
    """

    def __init__(
        self,
        n_trials: int = 100,
        loss_fn: str = "sharpe",
        sampler: str = "tpe",
        pruner: str = "median",
        seed: int = 42,
        timeout: Optional[int] = None,
        n_jobs: int = 1,
    ):
        self.n_trials = n_trials
        self.loss_fn = loss_fn
        self.sampler_name = sampler
        self.pruner_name = pruner
        self.seed = seed
        self.timeout = timeout
        self.n_jobs = n_jobs
        self._search_space: List[SearchSpace] = []
        self._study = None

    def add_param(self, name: str, param_type: str, **kwargs):
        """
        Register a hyperparameter to optimize.

        Args:
            name: Parameter name
            param_type: "int", "float", "log_float", "categorical"
            low/high: Range for numeric types
            choices: List for categorical type
        """
        self._search_space.append(SearchSpace(name=name, param_type=param_type, **kwargs))
        return self

    def add_model_space(self, model_name: str):
        """Add common hyperparameters for a model type."""
        common = {
            "bilstm": [
                SearchSpace("hidden_dim", "int", low=64, high=256),
                SearchSpace("num_layers", "int", low=1, high=3),
                SearchSpace("dropout", "float", low=0.1, high=0.4),
                SearchSpace("lr", "log_float", low=1e-5, high=1e-2),
            ],
            "dilated_cnn": [
                SearchSpace("channels", "int", low=32, high=128),
                SearchSpace("n_blocks", "int", low=2, high=6),
                SearchSpace("dropout", "float", low=0.1, high=0.4),
                SearchSpace("lr", "log_float", low=1e-5, high=1e-2),
            ],
            "lightgbm": [
                SearchSpace("num_leaves", "int", low=10, high=100),
                SearchSpace("n_estimators", "int", low=50, high=500),
                SearchSpace("learning_rate", "log_float", low=0.001, high=0.1),
                SearchSpace("max_depth", "int", low=3, high=12),
            ],
            "xgboost": [
                SearchSpace("n_estimators", "int", low=50, high=500),
                SearchSpace("max_depth", "int", low=3, high=10),
                SearchSpace("learning_rate", "log_float", low=0.001, high=0.1),
                SearchSpace("subsample", "float", low=0.5, high=1.0),
            ],
        }
        if model_name in common:
            self._search_space.extend(common[model_name])
        return self

    def optimize(
        self,
        objective_fn: Callable,
    ) -> HyperoptResult:
        """
        Run optimization.

        Args:
            objective_fn: Callable(trial) → float (loss to minimize).
                         The function receives an Optuna trial object and
                         should use self.suggest_params(trial) to get params.

        Returns:
            HyperoptResult with best params, score, and history.
        """
        try:
            import optuna
        except ImportError:
            raise ImportError("optuna required: pip install optuna>=3.0.0")

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        # Create sampler
        sampler = self._create_sampler(optuna)

        # Create pruner
        pruner = self._create_pruner(optuna)

        self._study = optuna.create_study(
            direction="minimize",
            sampler=sampler,
            pruner=pruner,
        )

        # Wrap objective to inject param suggestion
        def _wrapped_objective(trial):
            params = self._suggest_params(trial)
            return objective_fn(trial, params)

        self._study.optimize(
            _wrapped_objective,
            n_trials=self.n_trials,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            show_progress_bar=False,
        )

        # Build trial history
        history_rows = []
        for t in self._study.trials:
            row = {"trial": t.number, "score": t.value, "state": t.state.name}
            row.update(t.params)
            history_rows.append(row)

        history = pd.DataFrame(history_rows) if history_rows else pd.DataFrame()

        best = self._study.best_trial
        logger.info(
            f"Hyperopt complete: {len(self._study.trials)} trials, "
            f"best score={best.value:.4f}, params={best.params}"
        )

        return HyperoptResult(
            best_params=best.params,
            best_score=best.value,
            n_trials=len(self._study.trials),
            trial_history=history,
        )

    def _suggest_params(self, trial) -> Dict[str, Any]:
        """Suggest parameter values for a trial based on search space."""
        params = {}
        for sp in self._search_space:
            if sp.param_type == "int":
                params[sp.name] = trial.suggest_int(sp.name, sp.low, sp.high)
            elif sp.param_type == "float":
                params[sp.name] = trial.suggest_float(sp.name, sp.low, sp.high)
            elif sp.param_type == "log_float":
                params[sp.name] = trial.suggest_float(sp.name, sp.low, sp.high, log=True)
            elif sp.param_type == "categorical":
                params[sp.name] = trial.suggest_categorical(sp.name, sp.choices)
        return params

    def _create_sampler(self, optuna):
        if self.sampler_name == "tpe":
            return optuna.samplers.TPESampler(seed=self.seed)
        elif self.sampler_name == "cmaes":
            return optuna.samplers.CmaEsSampler(seed=self.seed)
        elif self.sampler_name == "grid":
            # Grid needs explicit search space — fallback to TPE
            return optuna.samplers.TPESampler(seed=self.seed)
        elif self.sampler_name == "random":
            return optuna.samplers.RandomSampler(seed=self.seed)
        return optuna.samplers.TPESampler(seed=self.seed)

    def _create_pruner(self, optuna):
        if self.pruner_name == "median":
            return optuna.pruners.MedianPruner()
        elif self.pruner_name == "percentile":
            return optuna.pruners.PercentilePruner(percentile=75.0)
        elif self.pruner_name == "none":
            return optuna.pruners.NopPruner()
        return optuna.pruners.MedianPruner()

    @staticmethod
    def compute_loss(metrics: Dict[str, float], loss_fn: str) -> float:
        """
        Compute loss value from backtest metrics.

        Args:
            metrics: Dict with sharpe_ratio, annual_return, max_drawdown, etc.
            loss_fn: "sharpe", "return", "risk_adjusted"

        Returns:
            Float loss (lower is better — negative Sharpe means maximize Sharpe).
        """
        if loss_fn == "sharpe":
            return -metrics.get("sharpe_ratio", 0.0)
        elif loss_fn == "return":
            return -metrics.get("annual_return", 0.0)
        elif loss_fn == "risk_adjusted":
            ret = metrics.get("annual_return", 0.0)
            dd = metrics.get("max_drawdown", 1.0)
            return -(ret - 2.0 * dd)
        return 0.0


__all__ = ["HyperoptEngine", "HyperoptResult", "SearchSpace"]
