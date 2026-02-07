import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from src.ml.models.lit import LiTModel
from loguru import logger
import sys

def generate_sine_wave_data(n_samples=1000, seq_len=50):
    """Generate synthetic sine wave data."""
    X = []
    y = []
    
    for _ in range(n_samples):
        start = np.random.rand() * 2 * np.pi
        t = np.linspace(start, start + 2 * np.pi, seq_len + 1)
        wave = np.sin(t)
        
        # Input: first seq_len points
        X.append(wave[:-1].reshape(-1, 1))
        # Target: last point (next step prediction)
        y.append(wave[-1].reshape(1))
        
    return torch.FloatTensor(np.array(X)), torch.FloatTensor(np.array(y))

def train_dummy():
    """Train LiT model on synthetic data to verify learning capability."""
    logger.info("Generating synthetic sine wave data...")
    X, y = generate_sine_wave_data()
    
    # Model config
    input_dim = 1
    d_model = 32
    model = LiTModel(input_dim=input_dim, d_model=d_model, nhead=2, num_encoder_layers=1, lstm_hidden_dim=32)
    
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    
    epochs = 10
    final_loss = 0.0
    
    logger.info(f"Starting dummy training for {epochs} epochs...")
    
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        output = model(X)
        loss = criterion(output, y)
        
        loss.backward()
        optimizer.step()
        
        logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.6f}")
        final_loss = loss.item()
        
    # Validation criteria: Loss should converge to near zero for a simple sine wave
    if final_loss < 0.1:
        logger.success(f"Dummy training SUCCESS. Final Loss: {final_loss:.6f}")
        sys.exit(0)
    else:
        logger.error(f"Dummy training FAILED. Loss didn't converge enough: {final_loss:.6f}")
        sys.exit(1)

if __name__ == "__main__":
    train_dummy()
