"""
Attention Seq2Seq Predictor — Encoder-Decoder with Bahdanau Attention.

Uses attention mechanism to weigh different timesteps
when making the final classification decision.

Ref: FUSION_PLAN Fase 3, item 3.5
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional, Dict, Any

from .base_predictor import BasePredictor


class _BahdanauAttention(nn.Module):
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.W = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.U = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.v = nn.Linear(hidden_dim, 1, bias=False)

    def forward(self, decoder_hidden: torch.Tensor, encoder_outputs: torch.Tensor):
        # decoder_hidden: (batch, hidden)
        # encoder_outputs: (batch, seq, hidden)
        score = self.v(torch.tanh(
            self.W(decoder_hidden).unsqueeze(1) + self.U(encoder_outputs)
        ))  # (batch, seq, 1)
        weights = F.softmax(score, dim=1)
        context = (weights * encoder_outputs).sum(dim=1)  # (batch, hidden)
        return context, weights.squeeze(-1)


class _Seq2SeqNet(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128,
                 num_layers: int = 2, n_classes: int = 3, dropout: float = 0.2):
        super().__init__()
        self.encoder = nn.LSTM(
            input_size=input_dim, hidden_size=hidden_dim,
            num_layers=num_layers, batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attention = _BahdanauAttention(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        enc_out, (h_n, _) = self.encoder(x)
        # Use last layer hidden as decoder query
        query = h_n[-1]  # (batch, hidden)
        context, _ = self.attention(query, enc_out)
        combined = torch.cat([query, context], dim=-1)
        return self.fc(self.dropout(combined))


class AttentionSeq2SeqPredictor(BasePredictor):
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
        self._model: Optional[_Seq2SeqNet] = None

    @property
    def name(self) -> str:
        return "attention_seq2seq"

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kwargs):
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        input_dim = X_train.shape[-1]
        self._model = _Seq2SeqNet(
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
            "hidden_dim": self.hidden_dim, "num_layers": self.num_layers,
            "lr": self.lr, "dropout": self.dropout, "epochs": self.epochs,
        }
