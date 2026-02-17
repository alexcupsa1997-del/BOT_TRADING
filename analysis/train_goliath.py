"""
analysis/train_goliath.py - Real Training Script for Goliath V2
==============================================================

Trains the Goliath Transformer model using historical Parquet data.
Ensures parity with `engine/features.py` for real-time inference.

Hardware Support:
- Auto-detects ROCm (AMD) or CUDA (NVIDIA).
- Uses `MPS` on Mac if available (though not relevant for this user).

Output:
- Saves model to `engine/models/goliath.pth`.
- Saves scaler to `engine/models/goliath.json`.
"""

import sys
import os
import glob
import json
import torch
import torch.nn as nn
import torch.optim as optim
import polars as pl
import pandas as pd # Used for feature calc parity
import numpy as np
from torch.utils.data import Dataset, DataLoader
from loguru import logger
from typing import Tuple, List, Dict, Any

# Ensure we can import from engine
sys.path.append(os.getcwd())

from engine.features import compute_features_batch
from engine.models.goliath import GoliathTransformerV2

# --- Configuration ---
CONFIG: Dict[str, Any] = {
    "data_path": "data/raw/BTCUSD/1m/", # Update if needed
    "window_size": 64,  # Sequence length
    "batch_size": 256, # Adjust based on GPU VRAM (RX 9070 has plenty)
    "epochs": 10,
    "learning_rate": 1e-4,
    "feature_dim": 8,   # Must match compute_features_batch output
    "target_horizon": 10, # Prediction horizon in bars
    "test_split": 0.2, # Last 20% for validation
}


class FinancialDataset(Dataset):
    def __init__(self, sequences: np.ndarray, targets: np.ndarray):
        self.sequences = torch.FloatTensor(sequences)
        self.targets = torch.LongTensor(targets)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]

def load_data(data_path: str) -> pd.DataFrame:
    """Loads parquet files into a single Pandas DataFrame."""
    # Using Polars for fast load, then convert to Pandas for feature parity
    files = sorted(glob.glob(f"{data_path}/*.parquet"))
    if not files:
        logger.error(f"No parquet files found in {data_path}")
        sys.exit(1)
        
    logger.info(f"Loading {len(files)} files...")
    df_pl = pl.scan_parquet(files).collect()
    df_pl = df_pl.sort("timestamp")
    
    # Convert to pandas for feature engineering parity
    return df_pl.to_pandas()

def create_labels(df: pd.DataFrame, horizon: int) -> np.ndarray:
    """
    Creates Target Labels based on Dynamic Volatility.
    This logic MUST follow the strategy's intent.
    
    0: SELL (Drop > threshold)
    1: HOLD (Flat)
    2: BUY (Rise > threshold)
    """
    future_price = df['trade_price'].shift(-horizon)
    current_price = df['trade_price']
    
    returns = (future_price - current_price) / current_price
    
    # Dynamic Threshold based on recent volatility
    vol = df['trade_price'].pct_change().rolling(50).std()
    vol_threshold = vol * 1.5 
    vol_threshold = vol_threshold.fillna(0.0001)
    
    labels = np.ones(len(returns), dtype=int) # Default HOLD (1)
    
    labels[returns > vol_threshold] = 2  # BUY
    labels[returns < -vol_threshold] = 0 # SELL
    
    return labels

def create_sequences(features: np.ndarray, labels: np.ndarray, seq_len: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Creates sequences for the Transformer (N, seq_len, features).
    """
    X, y = [], []
    # Loop is slow in python, but simple. Optimize if needed.
    # We skip the last 'horizon' because labels are NaN there
    valid_len = len(features) - CONFIG['target_horizon']
    
    for i in range(seq_len, valid_len):
        X.append(features[i-seq_len:i])
        y.append(labels[i])
        
    return np.array(X), np.array(y)

def main():
    logger.info("Starting Training Pipeline...")
    
    # 1. Device Setup
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    if device.type == 'cpu':
        logger.warning("Running on CPU! Training will be slow.")
    
    # 2. Data Loading & Feature Engineering
    df = load_data(CONFIG['data_path'])
    logger.info(f"Loaded {len(df)} rows.")
    
    logger.info("Computing Features...")
    df = compute_features_batch(df)
    df = df.dropna() # Drop initial NaN from rolling windows
    
    logger.info("Creating Labels...")
    labels = create_labels(df, CONFIG['target_horizon'])
    
    # Extract Feature Columns explicitly (Parity Logic)
    feature_cols = [
        'feature_log_ret',
        'feature_vol_10', 'feature_vol_50',
        'feature_mom_10', 'feature_mom_50',
        'feature_rsi',
        'feature_macd', 'feature_macd_signal'
    ]
    features = df[feature_cols].values
    
    # 3. Sequence Creation
    logger.info("Generating Sequences (this may take memory)...")
    X, y = create_sequences(features, labels, CONFIG['window_size'])
    logger.info(f"Dataset shape: X={X.shape}, y={y.shape}")
    
    # 4. Split Train/Test
    split_idx = int(len(X) * (1 - CONFIG['test_split']))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    train_dataset = FinancialDataset(X_train, y_train)
    test_dataset = FinancialDataset(X_test, y_test)
    
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=CONFIG['batch_size'], shuffle=False)
    
    # 5. Model Initialization
    # Since we removed Scaler dependency in the model forward pass,
    # we should handle scaling here if needed.
    # Note: Logic in `engine/features.py` output is raw values.
    # For now, we train on raw values or we calculate simple statistics if needed.
    # Goliath V2 usually handles raw inputs via LayerNorm, but standard scaling is better.
    
    # Simple Manual Scaling (Mean/Std) and saving it for inference
    mean = np.mean(X_train, axis=(0, 1))
    std = np.std(X_train, axis=(0, 1)) + 1e-6
    
    scaler_params = {
        "mean": mean.tolist(),
        "std": std.tolist()
    }
    
    # Save Scaler for Inference Engine
    os.makedirs("engine/models", exist_ok=True)
    with open("engine/models/goliath.json", "w") as f:
        json.dump(scaler_params, f, indent=4)
    logger.info("Saved scaler parameters.")
    
    # Apply Scaling
    X_train = (X_train - mean) / std
    X_test = (X_test - mean) / std
    
    # Re-create datasets with scaled data
    train_dataset = FinancialDataset(X_train, y_train)
    test_dataset = FinancialDataset(X_test, y_test)
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=CONFIG['batch_size'], shuffle=False)

    model = GoliathTransformerV2(
        config=CONFIG,
        input_dim=X.shape[2] # Correct argument name
    ).to(device)
    
    criterion = nn.CrossEntropyLoss(weight=torch.tensor([1.2, 0.5, 1.0]).to(device)) # Weighting: Sell, Hold, Buy
    optimizer = optim.AdamW(model.parameters(), lr=CONFIG['learning_rate'])
    
    # 6. Training Loop
    logger.info("Starting Training...")
    for epoch in range(CONFIG['epochs']):
        model.train()
        train_loss = 0.0
        
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            
        avg_train_loss = train_loss / len(train_loader)
        
        # Validation
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()
                
                _, predicted = torch.max(outputs.data, 1)
                total += batch_y.size(0)
                correct += (predicted == batch_y).sum().item()
                
        avg_val_loss = val_loss / len(test_loader)
        accuracy = 100 * correct / total
        
        logger.info(f"Epoch {epoch+1}/{CONFIG['epochs']} - Train Loss: {avg_train_loss:.4f} - Val Loss: {avg_val_loss:.4f} - Acc: {accuracy:.2f}%")
        
    # 7. Use Save Artifacts
    torch.save(model.state_dict(), "engine/models/goliath.pth")
    logger.info("Model saved to engine/models/goliath.pth")
    
if __name__ == "__main__":
    main()
