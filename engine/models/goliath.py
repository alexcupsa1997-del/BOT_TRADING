"""
engine/models/goliath.py - Model Architecture
=============================================

This file MUST match the training script's model definition exactly.
Any changes here must be replicated in `analysis/goliath_trainer_v2.py`.
"""

import torch
import torch.nn as nn
from typing import Dict, Any

class TrainingConfig:
    """Configuration placeholder to match training script structure."""
    def __init__(self):
        # Default config matching production defaults
        self.d_model = 256
        self.nhead = 8
        self.num_layers = 6
        self.dropout = 0.2
        self.sequence_length = 64

class GoliathTransformerV2(nn.Module):
    """
    Enhanced Transformer for trading signals.
    
    Triple-head output:
    - Direction (Buy/Sell/Hold)
    - TP/SL multipliers
    - Confidence score
    """
    
    def __init__(self, config: Any, input_dim: int):
        super().__init__()
        self.config = config
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, config.d_model)
        
        # Positional encoding
        self.pos_encoding = nn.Parameter(
            torch.randn(1, config.sequence_length, config.d_model) * 0.02
        )
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.d_model * 4,
            dropout=config.dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, config.num_layers)
        
        # Output heads
        self.direction_head = nn.Sequential(
            nn.Linear(config.d_model, 128),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(128, 3)  # Buy, Hold, Sell
        )
        
        self.tp_sl_head = nn.Sequential(
            nn.Linear(config.d_model, 64),
            nn.ReLU(),
            nn.Linear(64, 2),  # TP multiplier, SL multiplier
            nn.Sigmoid()  # 0-1 range, will scale to 1-5 ATR
        )
        
        self.confidence_head = nn.Sequential(
            nn.Linear(config.d_model, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            x: Input tensor (batch, seq_len, features)
            
        Returns:
            Dict with direction_logits, tp_sl, confidence
        """
        # Project input
        x = self.input_proj(x)
        # Handle pos_encoding slicing if input is shorter (though trained on fixed seq_len)
        seq_len = x.size(1)
        x = x + self.pos_encoding[:, :seq_len, :]
        
        # Transformer encoding
        x = self.transformer(x)
        
        # Use last token for prediction
        x = x[:, -1, :]
        
        return {
            'direction': self.direction_head(x),
            'tp_sl': self.tp_sl_head(x) * 4 + 1,  # Scale to 1-5 ATR
            'confidence': self.confidence_head(x).squeeze(-1)
        }
