"""
XGBoost Classifier — Alternative gradient boosting for tabular features.

Complements LightGBM with different tree-building strategy
(level-wise vs leaf-wise) for ensemble diversity.

Ref: FUSION_PLAN Fase 3, item 3.9
"""

from __future__ import annotations

import numpy as np
import joblib
from typing import Tuple, Optional, Dict, Any
from loguru import logger

from .base_predictor import BasePredictor


class XGBoostPredictor(BasePredictor):
    def __init__(self, n_estimators: int = 200, max_depth: int = 6,
                 learning_rate: float = 0.05, subsample: float = 0.8,
                 colsample_bytree: float = 0.8, min_child_weight: int = 5,
                 n_classes: int = 3, seed: int = 42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.min_child_weight = min_child_weight
        self.n_classes = n_classes
        self.seed = seed
        self._model = None
        self._label_map: dict | None = None
        self._inv_label_map: dict | None = None

    @property
    def name(self) -> str:
        return "xgboost"

    @property
    def is_sequence_model(self) -> bool:
        return False

    @staticmethod
    def _flatten(X: np.ndarray) -> np.ndarray:
        if X.ndim == 3:
            return X.reshape(X.shape[0], -1)
        return X

    def _remap_labels(self, y: np.ndarray) -> np.ndarray:
        """Remap labels to contiguous 0-indexed range for XGBoost."""
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
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost required: pip install xgboost>=2.0.0")

        X_flat = self._flatten(X_train)
        y_mapped = self._remap_labels(y_train)
        n_classes_actual = len(np.unique(y_mapped))

        self._model = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            min_child_weight=self.min_child_weight,
            objective="multi:softprob",
            num_class=n_classes_actual,
            eval_metric="mlogloss",
            random_state=self.seed,
            verbosity=0,
            n_jobs=-1,
        )

        eval_set = None
        if X_val is not None and y_val is not None:
            y_val_mapped = self._remap_labels(y_val)
            eval_set = [(self._flatten(X_val), y_val_mapped)]

        self._model.fit(
            X_flat, y_mapped,
            eval_set=eval_set,
            verbose=False,
        )

        return {"loss": 0.0}

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
            "n_estimators": self.n_estimators, "max_depth": self.max_depth,
            "learning_rate": self.learning_rate, "subsample": self.subsample,
        }
