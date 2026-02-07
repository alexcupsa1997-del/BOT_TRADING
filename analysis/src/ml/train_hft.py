"""
HFT Training Pipeline V2 (Multi-Scenario)

Orchestrates the training process across multiple market scenarios:
1. Loads ALL scenario_*.parquet files from data/
2. Combines them into a unified dataset
3. Trains the Goliath Transformer
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from loguru import logger
import sys
import os
import glob

# Add project root to path
sys.path.append(os.getcwd())

from analysis.src.quant.hft_features import HFTFeatureEngineer
from analysis.src.ml.models.goliath_transformer import GoliathTransformer, GoliathConfig

# --- CONFIGURATION ---
SEQ_LEN = 64
PREDICT_HORIZON = 5 
BATCH_SIZE = 64 # Increased batch size
EPOCHS = 10     # Increased epochs
LEARNING_RATE = 1e-4

def create_sequences(data: np.ndarray, targets: np.ndarray, seq_len: int):
    sequences = []
    labels = []
    for i in range(len(data) - seq_len):
        seq = data[i : i + seq_len]
        label = targets[i + seq_len - 1]
        sequences.append(seq)
        labels.append(label)
    return np.array(sequences), np.array(labels)

def create_labels(df: pd.DataFrame, horizon: int = 1, threshold: float = 0.0001):
    future_price = df['trade_price'].shift(-horizon)
    current_price = df['trade_price']
    returns = (future_price - current_price) / current_price
    labels = np.ones(len(returns)) # 1 = Hold
    labels[returns > threshold] = 2 # Up
    labels[returns < -threshold] = 0 # Down
    return labels[:-horizon]

def load_all_scenarios():
    """Loads and merges all scenario parquet files."""
    engineer = HFTFeatureEngineer()
    all_dfs = []
    
    files = glob.glob('data/scenario_*.parquet')
    if not files:
        logger.warning("No scenario files found! Falling back to synthetic_hft_ticks.parquet")
        files = glob.glob('data/synthetic_hft_ticks.parquet')
        
    for f in files:
        logger.info(f"Processing {f}...")
        df_raw = engineer.load_data(f)
        df_feat = engineer.compute_all_features(df_raw)
        
        # Labeling per file (to avoid boundary issues)
        labels = create_labels(df_feat, horizon=PREDICT_HORIZON)
        df_feat = df_feat.iloc[:len(labels)] # Trim features
        
        # Store features and labels together temporarily
        df_feat['__TARGET__'] = labels
        all_dfs.append(df_feat)
        
    if not all_dfs:
        raise ValueError("No data loaded.")
        
    full_df = pd.concat(all_dfs, ignore_index=True)
    return full_df

def main():
    logger.info("Starting Goliath HFT Training Pipeline V2 (Multi-Scenario)...")
    
    # 1. LOAD DATA
    full_df = load_all_scenarios()
    
    # Extract X and y
    feature_cols = [c for c in full_df.columns if 'feature_' in c]
    X_raw = full_df[feature_cols].values
    y_raw = full_df['__TARGET__'].values
    
    logger.info(f"Total Dataset Shape: {X_raw.shape}")
    
    # 2. SPLIT & NORMALIZE
    train_size = int(len(X_raw) * 0.8)
    X_train_raw, X_test_raw = X_raw[:train_size], X_raw[train_size:]
    y_train_raw, y_test_raw = y_raw[:train_size], y_raw[train_size:]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_raw)
    X_test_scaled = scaler.transform(X_test_raw)
    
    # 3. TENSOR CONSTRUCTION
    logger.info("Building tensors...")
    X_train, y_train = create_sequences(X_train_scaled, y_train_raw, SEQ_LEN)
    X_test, y_test = create_sequences(X_test_scaled, y_test_raw, SEQ_LEN)
    
    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train)), batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(TensorDataset(torch.FloatTensor(X_test), torch.LongTensor(y_test)), batch_size=BATCH_SIZE, shuffle=False)
    
    # 4. MODEL SETUP
    input_dim = X_train.shape[2]
    config = GoliathConfig(
        input_dim=input_dim,
        d_model=128,    # Larger model
        nhead=4,
        num_layers=3,   # Deeper model
        output_dim=3,
        max_seq_len=SEQ_LEN
    )
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Training on: {device} | Features: {input_dim}")
    
    model = GoliathTransformer(config).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    
    # 5. TRAINING LOOP
    best_acc = 0.0
    
    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0
        correct = 0
        total = 0
        
        for X_b, y_b in train_loader:
            X_b, y_b = X_b.to(device), y_b.to(device)
            optimizer.zero_grad()
            out = model(X_b)
            loss = criterion(out, y_b)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, pred = torch.max(out, 1)
            total += y_b.size(0)
            correct += (pred == y_b).sum().item()
            
        train_acc = 100 * correct / total
        
        # Validation
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for X_b, y_b in test_loader:
                X_b, y_b = X_b.to(device), y_b.to(device)
                out = model(X_b)
                _, pred = torch.max(out, 1)
                val_total += y_b.size(0)
                val_correct += (pred == y_b).sum().item()
        
        val_acc = 100 * val_correct / val_total
        logger.info(f"Epoch {epoch+1}/{EPOCHS} | Train Acc: {train_acc:.2f}% | Val Acc: {val_acc:.2f}%")
        
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), 'analysis/models_checkpoint/goliath_best.pth')
            
    logger.success(f"Training Complete. Best Validation Accuracy: {best_acc:.2f}%")

if __name__ == "__main__":
    main()