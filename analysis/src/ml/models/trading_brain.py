"""
TradingBrain — 4-Layer Multi-Expert Neural Architecture

Inspired by the CS2 RAP 6-Layer Coach (AI_BIOPSY.md §6.3), adapted for
financial time-series. Drops Position/Communication layers (no spatial
or coaching concepts in trading), keeping 4 specialized layers:

    Layer 1 — Perception  (Multi-Stream Input Encoding)
    Layer 2 — Memory      (LSTM + Self-Attention Fusion)
    Layer 3 — Strategy    (MoE with SuperpositionLayer Context Gating)
    Layer 4 — Decision    (Value Critic + Direction + Confidence)

Parameter count: ~2.4M at d_model=256.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import NamedTuple, Optional


# =============================================================================
# CONFIG
# =============================================================================

@dataclass
class TradingBrainConfig:
    """Configuration for the TradingBrain model."""
    # Input dimensions
    price_features: int = 5        # OHLCV
    n_indicators: int = 9          # From FeatureRegistry indicator count
    vol_features: int = 4          # volume, ATR, BB_bandwidth, returns

    # Model dimensions
    d_model: int = 256
    n_experts: int = 4             # Trend, MeanReversion, Breakout, Range
    expert_hidden: int = 128
    expert_output: int = 64

    # Memory layer
    lstm_hidden: int = 128
    lstm_layers: int = 2
    lstm_dropout: float = 0.2
    attn_heads: int = 4
    attn_dropout: float = 0.1

    # Context gating (SuperpositionLayer)
    context_dim: int = 0           # 0 = no external context

    # Decision layer
    n_classes: int = 3             # Long / Hold / Short

    # Regularization
    dropout: float = 0.1


# =============================================================================
# OUTPUT
# =============================================================================

class TradingBrainOutput(NamedTuple):
    """Output from a TradingBrain forward pass."""
    direction: torch.Tensor     # (batch, n_classes) — raw logits
    value: torch.Tensor         # (batch, 1) — expected return
    confidence: torch.Tensor    # (batch, 1) — [0, 1] sigmoid
    gate_weights: torch.Tensor  # (batch, n_experts) — MoE gate weights


# =============================================================================
# LAYER 1 — PERCEPTION
# =============================================================================

class PerceptionLayer(nn.Module):
    """Multi-stream input encoding: Price CNN + Indicator MLP + Vol MLP."""

    def __init__(self, cfg: TradingBrainConfig):
        super().__init__()
        # Price stream: 2-layer 1D CNN
        self.price_conv1 = nn.Conv1d(cfg.price_features, 64, kernel_size=3, padding=1)
        self.price_bn1 = nn.BatchNorm1d(64)
        self.price_conv2 = nn.Conv1d(64, 64, kernel_size=3, padding=1)
        self.price_bn2 = nn.BatchNorm1d(64)

        # Indicator stream: Linear projection
        self.ind_proj = nn.Linear(cfg.n_indicators, 96)
        self.ind_ln = nn.LayerNorm(96)
        self.ind_drop = nn.Dropout(cfg.dropout)

        # Volume/Volatility stream
        self.vol_proj = nn.Linear(cfg.vol_features, 32)
        self.vol_ln = nn.LayerNorm(32)

        # Fusion: 64 + 96 + 32 = 192 → d_model
        self.fusion = nn.Linear(192, cfg.d_model)
        self.fusion_ln = nn.LayerNorm(cfg.d_model)

    def forward(self, price: torch.Tensor, indicators: torch.Tensor,
                vol: torch.Tensor) -> torch.Tensor:
        """
        Args:
            price:      (batch, seq, 5)  — OHLCV
            indicators: (batch, seq, n_indicators)
            vol:        (batch, seq, 4)  — volume, ATR, BB_bw, returns
        Returns:
            (batch, seq, d_model)
        """
        # Price CNN: Conv1d expects (batch, channels, seq)
        p = price.permute(0, 2, 1)
        p = F.gelu(self.price_bn1(self.price_conv1(p)))
        p = F.gelu(self.price_bn2(self.price_conv2(p)))
        p = p.permute(0, 2, 1)  # back to (batch, seq, 64)

        # Indicator MLP
        ind = self.ind_drop(F.gelu(self.ind_ln(self.ind_proj(indicators))))

        # Vol MLP
        v = F.gelu(self.vol_ln(self.vol_proj(vol)))

        # Concatenate and fuse
        combined = torch.cat([p, ind, v], dim=-1)  # (batch, seq, 192)
        return self.fusion_ln(self.fusion(combined))


# =============================================================================
# LAYER 2 — MEMORY
# =============================================================================

class MemoryLayer(nn.Module):
    """Sequential LSTM + Associative Self-Attention, fused with residual."""

    def __init__(self, cfg: TradingBrainConfig):
        super().__init__()
        # Sequential memory
        self.lstm = nn.LSTM(
            input_size=cfg.d_model,
            hidden_size=cfg.lstm_hidden,
            num_layers=cfg.lstm_layers,
            batch_first=True,
            dropout=cfg.lstm_dropout if cfg.lstm_layers > 1 else 0.0,
        )

        # Associative memory (self-attention on LSTM output)
        self.attention = nn.MultiheadAttention(
            embed_dim=cfg.lstm_hidden,
            num_heads=cfg.attn_heads,
            dropout=cfg.attn_dropout,
            batch_first=True,
        )

        # Fusion: cat(lstm_out, attn_out) → d_model
        self.fusion = nn.Linear(cfg.lstm_hidden * 2, cfg.d_model)
        self.fusion_ln = nn.LayerNorm(cfg.d_model)

    def forward(self, x: torch.Tensor, perception_out: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq, d_model) — perception output
            perception_out: same tensor, for residual connection
        Returns:
            (batch, seq, d_model)
        """
        # LSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq, lstm_hidden)

        # Self-attention on LSTM output
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)

        # Fuse LSTM + Attention
        combined = torch.cat([lstm_out, attn_out], dim=-1)
        fused = F.gelu(self.fusion_ln(self.fusion(combined)))

        # Residual from perception
        return fused + perception_out


# =============================================================================
# LAYER 3 — STRATEGY (MoE + SuperpositionLayer)
# =============================================================================

class ExpertNetwork(nn.Module):
    """Single regime-specialized expert."""

    def __init__(self, d_model: int, hidden: int, output: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, hidden),
            nn.LayerNorm(hidden),
            nn.ReLU(),
            nn.Linear(hidden, output),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class SuperpositionLayer(nn.Module):
    """Context-gated masking (AI_BIOPSY.md §6.3.3)."""

    def __init__(self, d_model: int, context_dim: int):
        super().__init__()
        self.context_gate = nn.Linear(context_dim, d_model)

    def forward(self, x: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        gate = torch.sigmoid(self.context_gate(context))
        return x * gate


class StrategyLayer(nn.Module):
    """Mixture of Experts with optional context gating."""

    def __init__(self, cfg: TradingBrainConfig):
        super().__init__()
        self.n_experts = cfg.n_experts

        # Expert networks
        self.experts = nn.ModuleList([
            ExpertNetwork(cfg.d_model, cfg.expert_hidden, cfg.expert_output)
            for _ in range(cfg.n_experts)
        ])

        # Gating network
        self.gate = nn.Linear(cfg.d_model, cfg.n_experts)

        # Expert aggregation → d_model
        self.projection = nn.Linear(cfg.expert_output, cfg.d_model)
        self.proj_ln = nn.LayerNorm(cfg.d_model)

        # Optional SuperpositionLayer
        self.has_context = cfg.context_dim > 0
        if self.has_context:
            self.superposition = SuperpositionLayer(cfg.d_model, cfg.context_dim)

    def forward(self, memory_out: torch.Tensor,
                context: Optional[torch.Tensor] = None) -> tuple:
        """
        Args:
            memory_out: (batch, seq, d_model)
            context:    (batch, context_dim) or None
        Returns:
            (strategy_output, gate_weights)
            strategy_output: (batch, d_model)
            gate_weights:    (batch, n_experts)
        """
        # Use last timestep for decision
        last = memory_out[:, -1, :]  # (batch, d_model)

        # Gate weights
        gate_weights = F.softmax(self.gate(last), dim=-1)  # (batch, n_experts)

        # Expert outputs
        expert_outputs = torch.stack(
            [expert(last) for expert in self.experts], dim=1
        )  # (batch, n_experts, expert_output)

        # Weighted sum
        weights = gate_weights.unsqueeze(-1)  # (batch, n_experts, 1)
        weighted = (expert_outputs * weights).sum(dim=1)  # (batch, expert_output)

        # Project back to d_model
        output = self.proj_ln(self.projection(weighted))  # (batch, d_model)

        # Apply SuperpositionLayer if context provided
        if self.has_context and context is not None:
            output = self.superposition(output, context)

        return output, gate_weights


# =============================================================================
# LAYER 4 — DECISION
# =============================================================================

class DecisionLayer(nn.Module):
    """Value Critic + Direction + Confidence heads."""

    def __init__(self, cfg: TradingBrainConfig):
        super().__init__()
        # Value critic (expected return regression)
        self.value_head = nn.Sequential(
            nn.Linear(cfg.d_model, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

        # Direction head (Long/Hold/Short logits)
        self.direction_head = nn.Sequential(
            nn.Linear(cfg.d_model, 64),
            nn.ReLU(),
            nn.Linear(64, cfg.n_classes),
        )

        # Confidence head ([0, 1])
        self.confidence_head = nn.Sequential(
            nn.Linear(cfg.d_model, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, strategy_out: torch.Tensor) -> tuple:
        """
        Args:
            strategy_out: (batch, d_model)
        Returns:
            (direction, value, confidence)
        """
        direction = self.direction_head(strategy_out)
        value = self.value_head(strategy_out)
        confidence = self.confidence_head(strategy_out)
        return direction, value, confidence


# =============================================================================
# FULL MODEL
# =============================================================================

class TradingBrain(nn.Module):
    """
    4-Layer Multi-Expert Trading Model.

    Input streams are split before calling forward:
        price      — (batch, seq, 5)
        indicators — (batch, seq, n_indicators)
        vol        — (batch, seq, 4)
        context    — (batch, context_dim) [optional]
    """

    def __init__(self, cfg: TradingBrainConfig):
        super().__init__()
        self.cfg = cfg
        self.perception = PerceptionLayer(cfg)
        self.memory = MemoryLayer(cfg)
        self.strategy = StrategyLayer(cfg)
        self.decision = DecisionLayer(cfg)

    def forward(self, price: torch.Tensor, indicators: torch.Tensor,
                vol: torch.Tensor,
                context: Optional[torch.Tensor] = None) -> TradingBrainOutput:
        """
        Full forward pass through all 4 layers.

        Args:
            price:      (batch, seq, 5)
            indicators: (batch, seq, n_indicators)
            vol:        (batch, seq, 4)
            context:    (batch, context_dim) or None
        """
        # Layer 1 — Perception
        perceived = self.perception(price, indicators, vol)

        # Layer 2 — Memory
        remembered = self.memory(perceived, perceived)

        # Layer 3 — Strategy
        strategy_out, gate_weights = self.strategy(remembered, context)

        # Layer 4 — Decision
        direction, value, confidence = self.decision(strategy_out)

        return TradingBrainOutput(
            direction=direction,
            value=value,
            confidence=confidence,
            gate_weights=gate_weights,
        )


# =============================================================================
# COMPOSITE LOSS
# =============================================================================

class TradingBrainLoss(nn.Module):
    """
    Composite loss from AI_BIOPSY.md §7:
        L_total = L_direction + 0.5 × L_value + 0.3 × L_confidence + 1e-4 × L_sparsity
    """

    def __init__(self, label_smoothing: float = 0.1, value_weight: float = 0.5,
                 confidence_weight: float = 0.3, sparsity_weight: float = 1e-4):
        super().__init__()
        self.direction_loss = nn.CrossEntropyLoss(label_smoothing=label_smoothing)
        self.value_loss = nn.MSELoss()
        self.confidence_loss = nn.BCELoss()
        self.value_weight = value_weight
        self.confidence_weight = confidence_weight
        self.sparsity_weight = sparsity_weight

    def forward(self, output: TradingBrainOutput,
                direction_label: torch.Tensor,
                return_value: torch.Tensor,
                was_correct: torch.Tensor) -> torch.Tensor:
        """
        Args:
            output: TradingBrainOutput from model forward pass
            direction_label: (batch,) long — class indices
            return_value:    (batch,) float — expected return
            was_correct:     (batch,) float — 1.0 if direction correct, else 0.0
        """
        l_dir = self.direction_loss(output.direction, direction_label)
        l_val = self.value_loss(output.value.squeeze(-1), return_value)
        l_conf = self.confidence_loss(output.confidence.squeeze(-1), was_correct)
        l_sparse = output.gate_weights.abs().mean()

        return (l_dir
                + self.value_weight * l_val
                + self.confidence_weight * l_conf
                + self.sparsity_weight * l_sparse)
