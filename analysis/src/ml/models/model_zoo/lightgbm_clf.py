"""
LightGBM Classifier — Gradient boosting for tabular features.

Flattens sequence data into a single feature vector, then applies
LightGBM for classification. Excels at capturing non-linear
feature interactions without sequential structure.

Ref: FUSION_PLAN Fase 3, item 3.8
"""

from __future__ import annotations

import numpy as np
import joblib
from typing import Tuple, Optional, Dict, Any
from loguru import logger

from .base_predictor import BasePredictor


class LightGBMPredictor(BasePredictor):
    def __init__(self, num_leaves: int = 31, n_estimators: int = 200,
                 learning_rate: float = 0.05, max_depth: int = -1,
                 min_child_samples: int = 20, subsample: float = 0.8,
                 colsample_bytree: float = 0.8, n_classes: int = 3,
                 seed: int = 42):
        self.num_leaves = num_leaves
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_child_samples = min_child_samples
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.n_classes = n_classes
        self.seed = seed
        self._model = None
        self._label_map: dict | None = None
        self._inv_label_map: dict | None = None

    @property
    def name(self) -> str:
        return "lightgbm"

    @property
    def is_sequence_model(self) -> bool:
        return False

    @staticmethod
    def _flatten(X: np.ndarray) -> np.ndarray:
        """Flatten (n, seq, feat) → (n, seq*feat) for tabular model."""
        if X.ndim == 3:
            return X.reshape(X.shape[0], -1)
        return X

    def _remap_labels(self, y: np.ndarray) -> np.ndarray:
        """Remap labels to contiguous 0-indexed range."""
        unique = sorted(np.unique(y))
        if list(unique) == list(range(len(unique))):
            self._label_map = None
            self._inv_label_map = None
            return y
        self._label_map = {orig: idx for idx, orig in enumerate(unique)}
        self._inv_label_map = {idx: orig for orig, idx in self._label_map.items()}
        return np.array([self._label_map[v] for v in y])

    def _unmap_labels(self, preds: np.ndarray) -> np.ndarray:
        """Reverse the label remapping."""
        if self._inv_label_map is None:
            return preds
        return np.array([self._inv_label_map[v] for v in preds])

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kwargs):
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("lightgbm required: pip install lightgbm>=4.0.0")

        X_flat = self._flatten(X_train)
        y_mapped = self._remap_labels(y_train)
        n_classes_actual = len(np.unique(y_mapped))

        params = {
            "objective": "multiclass",
            "num_class": n_classes_actual,
            "metric": "multi_logloss",
            "num_leaves": self.num_leaves,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_child_samples": self.min_child_samples,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "random_state": self.seed,
            "verbosity": -1,
            "n_jobs": -1,
        }

        self._model = lgb.LGBMClassifier(
            n_estimators=self.n_estimators,
            **params,
        )

        eval_set = None
        if X_val is not None and y_val is not None:
            y_val_mapped = self._remap_labels(y_val)
            eval_set = [(self._flatten(X_val), y_val_mapped)]

        callbacks = [lgb.log_evaluation(period=0)]
        self._model.fit(
            X_flat, y_mapped,
            eval_set=eval_set,
            callbacks=callbacks,
        )

        best_score = self._model.best_score_
        loss = 0.0
        if best_score and "valid_0" in best_score:
            loss = best_score["valid_0"].get("multi_logloss", 0.0)

        return {"loss": loss}

    def predict(self, X) -> Tuple[np.ndarray, np.ndarray]:
        X_flat = self._flatten(X)
        probs = self._model.predict_proba(X_flat)
        preds_mapped = probs.argmax(axis=1)
        preds = self._unmap_labels(preds_mapped)
        confs = probs.max(axis=1)
        return preds.astype(int), confs.astype(float)

    def save(self, filepath: str):
        joblib.dump(self._model, filepath)

    def load(self, filepath: str):
        self._model = joblib.load(filepath)

    def get_params(self) -> Dict[str, Any]:
        return {
            "num_leaves": self.num_leaves, "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate, "max_depth": self.max_depth,
        }
