"""
Goliath Transformer Model

A PyTorch implementation of a Time-Series Transformer Encoder tailored for 
High-Frequency Trading (HFT) data.

Key Architecture:
- Inputs: Z-Scored feature tensors from HFTFeatureEngineer.
- Core: Multi-Head Self-Attention to detect non-linear dependencies across time steps.
- Output: Logits for Next-Event Prediction (e.g., Up/Down/Neutral).

Dependencies: torch
"""

import math
import torch
import torch.nn as nn
from dataclasses import dataclass

@dataclass
class GoliathConfig:
    input_dim: int          # Number of input features
    d_model: int = 256      # Doubled capacity (was 128)
    nhead: int = 8          # More attention heads (was 4)
    num_layers: int = 6     # Deeper network (was 3)
    dim_feedforward: int = 1024 # Larger brain
    dropout: float = 0.2
    output_dim: int = 3
    max_seq_len: int = 64
    context_dim: int = 0    # New: Extra dimension for global context (News/Macro)

class GoliathTransformer(nn.Module):
    def __init__(self, config: GoliathConfig):
        super().__init__()
        self.config = config
        
        # 1. Input Projection
        self.input_projection = nn.Linear(config.input_dim, config.d_model)
        
        # Context Projection (if news/macro data exists)
        if config.context_dim > 0:
            self.context_projection = nn.Linear(config.context_dim, config.d_model)
        
        # 2. Positional Encoding
        self.pos_encoder = PositionalEncoding(config.d_model, max_len=config.max_seq_len, dropout=config.dropout)
        
        # 3. Transformer Encoder Body
        encoder_layers = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=config.num_layers)
        
        # 4. Output Head
        self.decoder = nn.Linear(config.d_model, config.output_dim)
        
        self.init_weights()

    def init_weights(self):
        initrange = 0.1
        self.input_projection.bias.data.zero_()
        self.input_projection.weight.data.uniform_(-initrange, initrange)
        self.decoder.bias.data.zero_()
        self.decoder.weight.data.uniform_(-initrange, initrange)

    def forward(self, src: torch.Tensor, global_context: torch.Tensor = None) -> torch.Tensor:
        """
        Args:
            src: [Batch, Seq, Features]
            global_context: [Batch, Context_Dim] (Optional) - e.g., Sentiment Score
        """
        # Embed Features
        x = self.input_projection(src)
        
        # Fuse Global Context if provided (Add it to every time step)
        if self.config.context_dim > 0 and global_context is not None:
            ctx = self.context_projection(global_context) # [Batch, d_model]
            ctx = ctx.unsqueeze(1) # [Batch, 1, d_model]
            x = x + ctx # Broadcast addition: Context influences every tick
            
        x = x.permute(1, 0, 2)
        x = self.pos_encoder(x)
        x = x.permute(1, 0, 2)
        
        output = self.transformer_encoder(x)
        
        last_step_output = output[:, -1, :] 
        logits = self.decoder(last_step_output)
        return logits

if __name__ == "__main__":
    # --- SANITY CHECK ---
    print("Initializing Goliath Transformer...")
    
    # 1. Configuration
    # Assuming 10 features from our HFTFeatureEngineer
    cfg = GoliathConfig(input_dim=10, d_model=64, nhead=2, num_layers=2)
    model = GoliathTransformer(cfg)
    
    print(f"Model Architecture:\n{model}")
    
    # 2. Dummy Input Data
    # Batch Size=32, Sequence Length=50 ticks, Features=10
    batch_size = 32
    seq_len = 50
    dummy_input = torch.randn(batch_size, seq_len, cfg.input_dim)
    
    print(f"\nInput Shape: {dummy_input.shape}")
    
    # 3. Forward Pass
    try:
        output = model(dummy_input)
        print(f"Output Logits Shape: {output.shape}") # Should be [32, 3]
        
        # Check for NaNs
        if torch.isnan(output).any():
            print("CRITICAL: Output contains NaNs!")
        else:
            print("Forward pass successful. Signal flow verified.")
            
    except Exception as e:
        print(f"FAILED: {e}")
