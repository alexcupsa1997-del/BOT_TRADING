"""
BiLSTM Predictor — Bidirectional LSTM for sequence classification.

Captures both forward and backward temporal dependencies.

Ref: FUSION_PLAN Fase 3, item 3.4
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from typing import Tuple, Optional, Dict, Any
from loguru import logger

from .base_predictor import BasePredictor


class _BiLSTMNet(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128,
                 num_layers: int = 2, n_classes: int = 3, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim * 2, n_classes)  # *2 for bidirectional

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        last = out[:, -1, :]  # Last timestep
        return self.fc(self.dropout(last))


class BiLSTMPredictor(BasePredictor):
    def __init__(self, hidden_dim: int = 128, num_layers: int = 2,
                 n_classes: int = 3, dropout: float = 0.2,
                 lr: float = 1e-3, epochs: int = 50, batch_size: int = 64,
                 seed: int = 42):
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.n_classes = n_classes
        self.dropout = dropout
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self._model: Optional[_BiLSTMNet] = None

    @property
    def name(self) -> str:
        return "bilstm"

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kwargs):
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        input_dim = X_train.shape[-1]
        self._model = _BiLSTMNet(
            input_dim, self.hidden_dim, self.num_layers,
            self.n_classes, self.dropout,
        ).to(self.device)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=self.lr)
        criterion = nn.CrossEntropyLoss()

        X_t = torch.FloatTensor(X_train).to(self.device)
        y_t = torch.LongTensor(y_train).to(self.device)

        self._model.train()
        best_loss = float("inf")
        for epoch in range(self.epochs):
            perm = torch.randperm(len(X_t))
            epoch_loss = 0.0
            n_batches = 0
            for i in range(0, len(X_t), self.batch_size):
                idx = perm[i:i + self.batch_size]
                logits = self._model(X_t[idx])
                loss = criterion(logits, y_t[idx])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1
            avg_loss = epoch_loss / max(n_batches, 1)
            if avg_loss < best_loss:
                best_loss = avg_loss

        return {"loss": best_loss}

    def predict(self, X) -> Tuple[np.ndarray, np.ndarray]:
        self._model.eval()
        X_t = torch.FloatTensor(X).to(self.device)
        with torch.no_grad():
            logits = self._model(X_t)
            probs = torch.softmax(logits, dim=-1)
            preds = probs.argmax(dim=-1).cpu().numpy()
            confs = probs.max(dim=-1).values.cpu().numpy()
        return preds, confs

    def save(self, filepath: str):
        torch.save(self._model.state_dict(), filepath)

    def load(self, filepath: str):
        state = torch.load(filepath, map_location=self.device, weights_only=True)
        self._model.load_state_dict(state)

    def get_params(self) -> Dict[str, Any]:
        return {
            "hidden_dim": self.hidden_dim, "num_layers": self.num_layers,
            "lr": self.lr, "dropout": self.dropout, "epochs": self.epochs,
        }
