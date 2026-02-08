"""
LiT Model (Linear-transformer)

A hybrid architecture combining LSTM and Transformers for Time-Series Forecasting.
Reference: "LiT: Linear-transformer for Limit Order Book Prediction"

Architecture:
1. Input Layer: (Batch, Seq_Len, Features)
2. LSTM Component: Captures temporal dependencies and linear trends.
3. Transformer Component: Captures long-range dependencies and complex interactions via Self-Attention.
4. Fusion Layer: Combines outputs from LSTM and Transformer.
5. Output Layer: Predicts next price movement or spread.
"""

import torch
import torch.nn as nn
from typing import Optional

class LiTModel(nn.Module):
    def __init__(
        self,
        input_dim: int,
        d_model: int = 64,
        nhead: int = 4,
        num_encoder_layers: int = 2,
        lstm_hidden_dim: int = 64,
        lstm_layers: int = 1,
        dropout: float = 0.1,
        output_dim: int = 1,
    ):
        super().__init__()
        
        # 1. Embedding / Projection
        self.input_proj = nn.Linear(input_dim, d_model)
        
        # 2. Transformer Branch (Non-linear, Long-range)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)
        
        # 3. LSTM Branch (Linear, Temporal)
        self.lstm = nn.LSTM(
            input_size=d_model,
            hidden_size=lstm_hidden_dim,
            num_layers=lstm_layers,
            batch_first=True,
        )
        
        # 4. Fusion & Output
        # Combine (Batch, Seq, d_model) + (Batch, Seq, lstm_hidden) -> Output
        self.fusion = nn.Linear(d_model + lstm_hidden_dim, d_model)
        self.activation = nn.ReLU()
        
        self.output_head = nn.Linear(d_model, output_dim)
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            x: Input tensor of shape (Batch, Seq_Len, Input_Dim)
            mask: Optional mask for Transformer
            
        Returns:
            Output prediction (Batch, Output_Dim) - typically predicting the NEXT step
        """
        # (Batch, Seq, Input) -> (Batch, Seq, d_model)
        x_proj = self.input_proj(x)
        
        # Branch 1: Transformer
        # (Batch, Seq, d_model)
        transformer_out = self.transformer_encoder(x_proj, src_key_padding_mask=mask)
        
        # Branch 2: LSTM
        # LSTM returns (output, (h_n, c_n))
        # output shape: (Batch, Seq, lstm_hidden)
        lstm_out, _ = self.lstm(x_proj)
        
        # Fusion Strategy: Concatenate the final hidden states
        # We take the last time step for forecasting
        
        # (Batch, d_model)
        t_last = transformer_out[:, -1, :]
        
        # (Batch, lstm_hidden)
        l_last = lstm_out[:, -1, :]
        
        # Concatenate: (Batch, d_model + lstm_hidden)
        combined = torch.cat([t_last, l_last], dim=1)
        
        # Fuse and Project
        fused = self.activation(self.fusion(combined))
        
        # Final Output
        prediction = self.output_head(fused)
        
        return prediction
