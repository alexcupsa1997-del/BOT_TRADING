"""
EnsembleMetaLearner — 2-Level Stacking Ensemble

Level 0 (Base Models):
    Each model from MODEL_REGISTRY receives same features and produces
    (prediction, confidence) tuples.

Level 1 (Meta-Learner):
    Receives concatenated (pred_one_hot, conf) from each base model.
    Trained on out-of-fold predictions (walk-forward stacking).
    Options: LogisticRegression (default), small MLP.

Confidence Gate:
    < 0.6 → HOLD (skip trade)
    0.6 – 0.8 → trade with reduced size (50%)
    > 0.8 → trade with full size

Ref: FUSION_PLAN Fase 3, item 3.10
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from loguru import logger

from src.ml.models.model_zoo import MODEL_REGISTRY, get_model
from src.ml.models.model_zoo.base_predictor import BasePredictor


@dataclass
class EnsembleConfig:
    model_names: List[str] = field(default_factory=lambda: ["bilstm", "dilated_cnn", "lstm_attention"])
    model_kwargs: Dict[str, Dict] = field(default_factory=dict)
    meta_learner_type: str = "logistic"  # "logistic" | "mlp" | "weighted_avg"
    n_classes: int = 3
    confidence_gate_low: float = 0.6
    confidence_gate_high: float = 0.8
    seed: int = 42


class EnsembleMetaLearner:
    """
    2-level stacking ensemble with walk-forward training.

    Usage:
        ens = EnsembleMetaLearner(config)
        ens.fit(X_train, y_train)
        preds, confs, sizing = ens.predict(X_test)
        weights = ens.get_model_weights()
    """

    def __init__(self, config: EnsembleConfig | None = None):
        self.config = config or EnsembleConfig()
        self.base_models: List[BasePredictor] = []
        self._meta_model = None
        self._model_weights: Dict[str, float] = {}

        # Instantiate base models
        for name in self.config.model_names:
            kwargs = self.config.model_kwargs.get(name, {})
            kwargs.setdefault("seed", self.config.seed)
            kwargs.setdefault("n_classes", self.config.n_classes)
            model = get_model(name, **kwargs)
            self.base_models.append(model)

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Train all base models, then train meta-learner on their predictions.

        If X_val/y_val provided, uses them for meta-learner training.
        Otherwise splits X_train into base training + meta training.
        """
        np.random.seed(self.config.seed)

        # Split for meta-learner if no validation set
        if X_val is None:
            split = int(len(X_train) * 0.8)
            X_base, y_base = X_train[:split], y_train[:split]
            X_meta, y_meta = X_train[split:], y_train[split:]
        else:
            X_base, y_base = X_train, y_train
            X_meta, y_meta = X_val, y_val

        # -- Level 0: Train base models --
        for model in self.base_models:
            logger.info(f"Training base model: {model.name}")
            model.fit(X_base, y_base)

        # -- Collect out-of-sample predictions for meta-learner --
        meta_features = self._collect_meta_features(X_meta)

        # -- Level 1: Train meta-learner --
        self._fit_meta(meta_features, y_meta)

        # -- Compute model weights for interpretability --
        self._compute_weights(meta_features, y_meta)

        return {"n_base_models": len(self.base_models)}

    def fit_walk_forward(
        self,
        X: np.ndarray,
        y: np.ndarray,
        folds: list,
    ) -> Dict[str, float]:
        """
        Train with walk-forward stacking (proper out-of-fold predictions).

        Args:
            X: Full feature array
            y: Full label array
            folds: List of Fold objects from WalkForwardValidator
        """
        np.random.seed(self.config.seed)
        all_meta_features = []
        all_meta_labels = []

        for fold in folds:
            X_train_fold = X[fold.train_indices]
            y_train_fold = y[fold.train_indices]
            X_test_fold = X[fold.test_indices]
            y_test_fold = y[fold.test_indices]

            # Train base models on this fold's training data
            for model in self.base_models:
                model.fit(X_train_fold, y_train_fold)

            # Collect out-of-fold predictions
            meta_feat = self._collect_meta_features(X_test_fold)
            all_meta_features.append(meta_feat)
            all_meta_labels.append(y_test_fold)

        # Concatenate all out-of-fold predictions
        combined_features = np.vstack(all_meta_features)
        combined_labels = np.concatenate(all_meta_labels)

        # Retrain base models on full data for production
        for model in self.base_models:
            model.fit(X, y)

        # Train meta-learner on out-of-fold predictions
        self._fit_meta(combined_features, combined_labels)
        self._compute_weights(combined_features, combined_labels)

        return {"n_folds": len(folds), "n_meta_samples": len(combined_labels)}

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate ensemble predictions.

        Returns:
            (predictions, confidences, position_sizing)
            predictions: (n,) int array in {0, 1, 2}
            confidences: (n,) float array in [0, 1]
            position_sizing: (n,) float array — 0.0, 0.5, or 1.0
        """
        meta_features = self._collect_meta_features(X)

        if self._meta_model is not None:
            probs = self._meta_model.predict_proba(meta_features)
            preds = probs.argmax(axis=1)
            confs = probs.max(axis=1)
        else:
            # Fallback: majority vote
            preds, confs = self._majority_vote(X)

        # Apply confidence gate
        sizing = np.ones(len(confs))
        sizing[confs < self.config.confidence_gate_high] = 0.5
        sizing[confs < self.config.confidence_gate_low] = 0.0

        # Override to HOLD where sizing is 0
        preds[sizing == 0.0] = 0

        return preds.astype(int), confs.astype(float), sizing.astype(float)

    def get_model_weights(self) -> Dict[str, float]:
        """Return each base model's weight in the meta-learner."""
        return dict(self._model_weights)

    # -----------------------------------------------------------------
    # INTERNAL
    # -----------------------------------------------------------------

    def _collect_meta_features(self, X: np.ndarray) -> np.ndarray:
        """
        Get predictions from all base models, format for meta-learner.

        Meta-feature per model: [pred_class_0, pred_class_1, pred_class_2, confidence]
        → Total features = n_models * (n_classes + 1)
        """
        features_list = []
        for model in self.base_models:
            preds, confs = model.predict(X)
            # One-hot encode predictions
            one_hot = np.zeros((len(preds), self.config.n_classes))
            for i, p in enumerate(preds):
                one_hot[i, int(p)] = 1.0
            # Append confidence
            feat = np.column_stack([one_hot, confs])
            features_list.append(feat)

        return np.hstack(features_list)

    def _fit_meta(self, meta_features: np.ndarray, y: np.ndarray):
        """Train the Level-1 meta-learner."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.neural_network import MLPClassifier

        if self.config.meta_learner_type == "logistic":
            self._meta_model = LogisticRegression(
                max_iter=1000, random_state=self.config.seed,
            )
        elif self.config.meta_learner_type == "mlp":
            self._meta_model = MLPClassifier(
                hidden_layer_sizes=(32, 16), max_iter=500,
                random_state=self.config.seed,
            )
        else:
            # weighted_avg: no sklearn model, use majority vote
            self._meta_model = None
            return

        self._meta_model.fit(meta_features, y)

    def _compute_weights(self, meta_features: np.ndarray, y: np.ndarray):
        """Compute interpretable weight per base model."""
        n_models = len(self.base_models)
        feat_per_model = self.config.n_classes + 1

        accuracies = []
        for i, model in enumerate(self.base_models):
            start = i * feat_per_model
            # The prediction is argmax of one-hot columns
            one_hot = meta_features[:, start:start + self.config.n_classes]
            model_preds = one_hot.argmax(axis=1)
            acc = (model_preds == y).mean()
            accuracies.append(acc)

        total = sum(accuracies) if sum(accuracies) > 0 else 1.0
        self._model_weights = {
            model.name: acc / total
            for model, acc in zip(self.base_models, accuracies)
        }

    def _majority_vote(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Fallback: weighted majority vote."""
        n = X.shape[0]
        votes = np.zeros((n, self.config.n_classes))

        for model in self.base_models:
            preds, confs = model.predict(X)
            weight = self._model_weights.get(model.name, 1.0 / len(self.base_models))
            for i in range(n):
                votes[i, int(preds[i])] += confs[i] * weight

        preds = votes.argmax(axis=1)
        total_votes = votes.sum(axis=1)
        confs = votes.max(axis=1) / np.where(total_votes > 0, total_votes, 1.0)
        return preds, confs


__all__ = ["EnsembleConfig", "EnsembleMetaLearner"]
