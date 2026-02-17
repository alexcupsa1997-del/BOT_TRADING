"""
BasePredictor — Abstract base class for all Model Zoo models.

Every model in the zoo must implement this interface to ensure
consistent fit/predict/save/load behavior across neural nets,
tree-based models, and RL agents.

Ref: FUSION_PLAN Fase 3
"""

from __future__ import annotations

import numpy as np
import torch
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any


class BasePredictor(ABC):
    """
    Uniform interface for all predictive models.

    Contract:
        - fit(X, y) trains the model
        - predict(X) returns (predictions, confidences)
        - predictions: int array with values in {0, 1, 2}
          (0=HOLD, 1=BUY/LONG, 2=SELL/SHORT)
        - confidences: float array in [0, 1]
    """

    @abstractmethod
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict[str, float]:
        """
        Train the model.

        Args:
            X_train: Training features.
                     Shape (n, seq_len, n_features) for sequence models
                     or (n, n_features) for tabular models.
            y_train: Labels in {0, 1, 2}.
            X_val: Optional validation features.
            y_val: Optional validation labels.

        Returns:
            Dict of training metrics (e.g. {'loss': 0.5, 'accuracy': 0.7}).
        """
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate predictions.

        Args:
            X: Features, same shape convention as fit.

        Returns:
            (predictions, confidences)
            predictions: (n,) int array in {0, 1, 2}
            confidences: (n,) float array in [0, 1]
        """
        ...

    @abstractmethod
    def save(self, filepath: str) -> None:
        """Persist model to disk."""
        ...

    @abstractmethod
    def load(self, filepath: str) -> None:
        """Load model from disk."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique model identifier (e.g. 'bilstm', 'lightgbm')."""
        ...

    @property
    def device(self) -> str:
        return "cuda" if torch.cuda.is_available() else "cpu"

    @property
    def is_sequence_model(self) -> bool:
        """True if model expects (batch, seq, feat) input."""
        return True

    def get_params(self) -> Dict[str, Any]:
        """Return current hyperparameters for logging/hyperopt."""
        return {}
