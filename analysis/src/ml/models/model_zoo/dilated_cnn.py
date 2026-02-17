"""
Dilated CNN Predictor — WaveNet-style temporal convolutions.

Uses exponentially increasing dilation rates to capture
multi-scale temporal patterns without pooling.

Ref: FUSION_PLAN Fase 3, item 3.6
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from typing import Tuple, Optional, Dict, Any

from .base_predictor import BasePredictor


class _DilatedBlock(nn.Module):
    """Single dilated causal convolution block with residual."""
    def __init__(self, channels: int, kernel_size: int, dilation: int, dropout: float):
        super().__init__()
        padding = (kernel_size - 1) * dilation  # causal padding
        self.conv = nn.Conv1d(channels, channels, kernel_size,
                              dilation=dilation, padding=padding)
        self.gate_conv = nn.Conv1d(channels, channels, kernel_size,
                                   dilation=dilation, padding=padding)
        self.dropout = nn.Dropout(dropout)
        self.residual = nn.Conv1d(channels, channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, channels, seq)
        h = torch.tanh(self.conv(x)[..., :x.size(-1)])
        g = torch.sigmoid(self.gate_conv(x)[..., :x.size(-1)])
        out = self.dropout(h * g)
        return self.residual(out) + x


class _DilatedCNNNet(nn.Module):
    def __init__(self, input_dim: int, channels: int = 64,
                 kernel_size: int = 3, n_blocks: int = 4,
                 n_classes: int = 3, dropout: float = 0.2):
        super().__init__()
        self.input_proj = nn.Conv1d(input_dim, channels, 1)
        self.blocks = nn.ModuleList([
            _DilatedBlock(channels, kernel_size, dilation=2**i, dropout=dropout)
            for i in range(n_blocks)
        ])
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Sequential(
            nn.Linear(channels, channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(channels // 2, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq, feat) → transpose to (batch, feat, seq)
        x = x.permute(0, 2, 1)
        x = self.input_proj(x)
        for block in self.blocks:
            x = block(x)
        x = self.global_pool(x).squeeze(-1)  # (batch, channels)
        return self.classifier(x)


class DilatedCNNPredictor(BasePredictor):
    def __init__(self, channels: int = 64, kernel_size: int = 3,
                 n_blocks: int = 4, n_classes: int = 3, dropout: float = 0.2,
                 lr: float = 1e-3, epochs: int = 50, batch_size: int = 64,
                 seed: int = 42):
        self.channels = channels
        self.kernel_size = kernel_size
        self.n_blocks = n_blocks
        self.n_classes = n_classes
        self.dropout = dropout
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self._model: Optional[_DilatedCNNNet] = None

    @property
    def name(self) -> str:
        return "dilated_cnn"

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kwargs):
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        input_dim = X_train.shape[-1]
        self._model = _DilatedCNNNet(
            input_dim, self.channels, self.kernel_size,
            self.n_blocks, self.n_classes, self.dropout,
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
            avg = epoch_loss / max(n_batches, 1)
            if avg < best_loss:
                best_loss = avg

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
            "channels": self.channels, "kernel_size": self.kernel_size,
            "n_blocks": self.n_blocks, "lr": self.lr, "epochs": self.epochs,
        }
