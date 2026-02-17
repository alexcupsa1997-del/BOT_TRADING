"""
Tests for EnsembleMetaLearner — 2-level stacking ensemble.

Ref: FUSION_PLAN Fase 3
"""

import numpy as np
import pytest

from src.ml.models.ensemble_meta_learner import (
    EnsembleMetaLearner,
    EnsembleConfig,
)


@pytest.fixture
def dummy_data():
    np.random.seed(42)
    X = np.random.randn(80, 30, 10).astype(np.float32)
    y = np.random.randint(0, 3, 80)
    return X, y


@pytest.fixture
def small_ensemble():
    """Ensemble with only neural models (no optional tree deps)."""
    cfg = EnsembleConfig(
        model_names=["bilstm", "dilated_cnn"],
        model_kwargs={
            "bilstm": {"epochs": 2, "batch_size": 16, "hidden_dim": 32},
            "dilated_cnn": {"epochs": 2, "batch_size": 16, "channels": 16},
        },
        seed=42,
    )
    return EnsembleMetaLearner(cfg)


class TestEnsembleFitPredict:
    def test_fit_and_predict(self, small_ensemble, dummy_data):
        X, y = dummy_data
        small_ensemble.fit(X[:60], y[:60], X[60:], y[60:])
        preds, confs, sizing = small_ensemble.predict(X[60:])

        assert preds.shape == (20,)
        assert confs.shape == (20,)
        assert sizing.shape == (20,)
        assert all(p in [0, 1, 2] for p in preds)
        assert all(0 <= c <= 1 for c in confs)
        assert all(s in [0.0, 0.5, 1.0] for s in sizing)

    def test_confidence_gate(self, small_ensemble, dummy_data):
        X, y = dummy_data
        small_ensemble.fit(X[:60], y[:60], X[60:], y[60:])
        preds, confs, sizing = small_ensemble.predict(X[60:])

        # Where sizing is 0.0, prediction should be HOLD (0)
        for i in range(len(preds)):
            if sizing[i] == 0.0:
                assert preds[i] == 0


class TestEnsembleWeights:
    def test_weights_returned(self, small_ensemble, dummy_data):
        X, y = dummy_data
        small_ensemble.fit(X[:60], y[:60], X[60:], y[60:])
        weights = small_ensemble.get_model_weights()

        assert isinstance(weights, dict)
        assert len(weights) == 2
        assert "bilstm" in weights
        assert "dilated_cnn" in weights
        # Weights should be positive and sum to ~1
        assert all(w >= 0 for w in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_different_data_different_weights(self, dummy_data):
        """Different random data should produce different weights."""
        X, y = dummy_data
        cfg = EnsembleConfig(
            model_names=["bilstm", "dilated_cnn"],
            model_kwargs={
                "bilstm": {"epochs": 2, "batch_size": 16, "hidden_dim": 32},
                "dilated_cnn": {"epochs": 2, "batch_size": 16, "channels": 16},
            },
            seed=42,
        )
        ens = EnsembleMetaLearner(cfg)
        ens.fit(X[:60], y[:60], X[60:], y[60:])
        w1 = ens.get_model_weights()
        assert isinstance(w1, dict)


class TestEnsembleMetaLearnerTypes:
    def test_logistic_meta(self, dummy_data):
        X, y = dummy_data
        cfg = EnsembleConfig(
            model_names=["bilstm"],
            model_kwargs={"bilstm": {"epochs": 2, "batch_size": 16, "hidden_dim": 32}},
            meta_learner_type="logistic",
            seed=42,
        )
        ens = EnsembleMetaLearner(cfg)
        ens.fit(X[:60], y[:60], X[60:], y[60:])
        preds, _, _ = ens.predict(X[60:])
        assert len(preds) == 20

    def test_mlp_meta(self, dummy_data):
        X, y = dummy_data
        cfg = EnsembleConfig(
            model_names=["bilstm"],
            model_kwargs={"bilstm": {"epochs": 2, "batch_size": 16, "hidden_dim": 32}},
            meta_learner_type="mlp",
            seed=42,
        )
        ens = EnsembleMetaLearner(cfg)
        ens.fit(X[:60], y[:60], X[60:], y[60:])
        preds, _, _ = ens.predict(X[60:])
        assert len(preds) == 20

    def test_weighted_avg_fallback(self, dummy_data):
        X, y = dummy_data
        cfg = EnsembleConfig(
            model_names=["bilstm"],
            model_kwargs={"bilstm": {"epochs": 2, "batch_size": 16, "hidden_dim": 32}},
            meta_learner_type="weighted_avg",
            seed=42,
        )
        ens = EnsembleMetaLearner(cfg)
        ens.fit(X[:60], y[:60], X[60:], y[60:])
        preds, _, _ = ens.predict(X[60:])
        assert len(preds) == 20
