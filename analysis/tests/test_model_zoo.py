"""
Tests for Model Zoo — All models implement BasePredictor correctly.

Ref: FUSION_PLAN Fase 3
"""

import numpy as np
import pytest
import torch

from src.ml.models.model_zoo import MODEL_REGISTRY, get_model
from src.ml.models.model_zoo.base_predictor import BasePredictor


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def dummy_seq_data():
    """Synthetic sequential data: (batch=48, seq=30, feat=10), labels in {0,1,2}."""
    np.random.seed(42)
    X = np.random.randn(48, 30, 10).astype(np.float32)
    y = np.random.randint(0, 3, 48)
    return X, y


@pytest.fixture
def dummy_split(dummy_seq_data):
    """Train/test split."""
    X, y = dummy_seq_data
    return X[:32], y[:32], X[32:], y[32:]


NEURAL_MODELS = ["bilstm", "attention_seq2seq", "dilated_cnn", "lstm_attention"]
# Tree models need optional deps, test separately
TREE_MODELS = ["lightgbm", "xgboost"]


# =============================================================================
# REGISTRY TESTS
# =============================================================================

class TestModelRegistry:
    def test_registry_has_all_models(self):
        expected = {"bilstm", "attention_seq2seq", "dilated_cnn",
                    "lstm_attention", "lightgbm", "xgboost"}
        assert expected == set(MODEL_REGISTRY.keys())

    def test_get_model_returns_base_predictor(self):
        model = get_model("bilstm", epochs=1)
        assert isinstance(model, BasePredictor)

    def test_get_model_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("nonexistent")

    def test_all_models_have_name(self):
        for name, cls in MODEL_REGISTRY.items():
            model = cls(epochs=1, n_classes=3, seed=42) if name in NEURAL_MODELS else cls(n_classes=3, seed=42)
            assert model.name == name


# =============================================================================
# NEURAL MODEL TESTS
# =============================================================================

class TestNeuralModels:
    @pytest.mark.parametrize("model_name", NEURAL_MODELS)
    def test_fit_and_predict(self, model_name, dummy_split):
        X_train, y_train, X_test, y_test = dummy_split
        model = get_model(model_name, epochs=2, batch_size=16, seed=42)
        metrics = model.fit(X_train, y_train)
        assert isinstance(metrics, dict)
        assert "loss" in metrics

        preds, confs = model.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert confs.shape == (len(X_test),)
        assert all(p in [0, 1, 2] for p in preds)
        assert all(0 <= c <= 1 for c in confs)

    @pytest.mark.parametrize("model_name", NEURAL_MODELS)
    def test_is_sequence_model(self, model_name):
        model = get_model(model_name, epochs=1)
        assert model.is_sequence_model is True

    @pytest.mark.parametrize("model_name", NEURAL_MODELS)
    def test_reproducibility(self, model_name, dummy_split):
        X_train, y_train, X_test, y_test = dummy_split
        m1 = get_model(model_name, epochs=2, batch_size=16, seed=42)
        m1.fit(X_train, y_train)
        p1, c1 = m1.predict(X_test)

        m2 = get_model(model_name, epochs=2, batch_size=16, seed=42)
        m2.fit(X_train, y_train)
        p2, c2 = m2.predict(X_test)

        np.testing.assert_array_equal(p1, p2)
        np.testing.assert_array_almost_equal(c1, c2, decimal=4)

    @pytest.mark.parametrize("model_name", NEURAL_MODELS)
    def test_get_params(self, model_name):
        model = get_model(model_name, epochs=1)
        params = model.get_params()
        assert isinstance(params, dict)
        assert "lr" in params


# =============================================================================
# TREE MODEL TESTS (optional deps)
# =============================================================================

class TestTreeModels:
    @pytest.mark.parametrize("model_name", TREE_MODELS)
    def test_fit_and_predict(self, model_name, dummy_split):
        X_train, y_train, X_test, y_test = dummy_split
        try:
            model = get_model(model_name, n_estimators=10, seed=42)
        except ImportError:
            pytest.skip(f"{model_name} not installed")

        model.fit(X_train, y_train)
        preds, confs = model.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert confs.shape == (len(X_test),)
        assert all(p in [0, 1, 2] for p in preds)
        assert all(0 <= c <= 1 for c in confs)

    @pytest.mark.parametrize("model_name", TREE_MODELS)
    def test_is_not_sequence_model(self, model_name):
        try:
            model = get_model(model_name)
        except ImportError:
            pytest.skip(f"{model_name} not installed")
        assert model.is_sequence_model is False

    @pytest.mark.parametrize("model_name", TREE_MODELS)
    def test_handles_3d_input(self, model_name, dummy_split):
        """Tree models should auto-flatten (n, seq, feat) → (n, seq*feat)."""
        X_train, y_train, X_test, y_test = dummy_split
        try:
            model = get_model(model_name, n_estimators=10, seed=42)
        except ImportError:
            pytest.skip(f"{model_name} not installed")

        model.fit(X_train, y_train)
        preds, _ = model.predict(X_test)
        assert preds.shape == (len(X_test),)


# =============================================================================
# RL AGENT TESTS
# =============================================================================

class TestRLAgent:
    def test_dqn_fit_and_predict(self, dummy_split):
        from src.ml.models.rl_agent import DQNAgent, DQNConfig

        X_train, y_train, X_test, y_test = dummy_split
        agent = DQNAgent(DQNConfig(
            variant="dqn", hidden_dim=32, lr=1e-3,
            epsilon_decay_steps=100, seed=42,
        ))
        metrics = agent.fit(X_train, y_train, n_episodes=1)
        assert "loss" in metrics

        preds, confs = agent.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert all(0 <= c <= 1 for c in confs)

    def test_double_dqn(self, dummy_split):
        from src.ml.models.rl_agent import DQNAgent, DQNConfig

        X_train, y_train, X_test, _ = dummy_split
        agent = DQNAgent(DQNConfig(variant="double", hidden_dim=32, seed=42))
        agent.fit(X_train, y_train, n_episodes=1)
        preds, confs = agent.predict(X_test)
        assert preds.shape == (len(X_test),)

    def test_dueling_dqn(self, dummy_split):
        from src.ml.models.rl_agent import DQNAgent, DQNConfig

        X_train, y_train, X_test, _ = dummy_split
        agent = DQNAgent(DQNConfig(variant="dueling", hidden_dim=32, seed=42))
        agent.fit(X_train, y_train, n_episodes=1)
        preds, confs = agent.predict(X_test)
        assert preds.shape == (len(X_test),)

    def test_rl_ensemble(self, dummy_split):
        from src.ml.models.rl_agent import RLEnsemble

        X_train, y_train, X_test, _ = dummy_split
        ensemble = RLEnsemble(seed=42, hidden_dim=32, epsilon_decay_steps=100)
        ensemble.fit(X_train, y_train, n_episodes=1)
        preds, confs = ensemble.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert all(p in [0, 1, 2] for p in preds)
