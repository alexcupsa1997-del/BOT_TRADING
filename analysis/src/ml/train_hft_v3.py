"""
HFT Training Pipeline V3 (Pro)

Advanced training with:
- Dynamic Volatility-Based Labeling
- Class Weighting (Imbalance handling)
- Learning Rate Scheduling (OneCycle)
- Deeper Regularization
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from loguru import logger
import sys
import os

# Add project root
sys.path.append(os.getcwd())

from src.quant.hft_features import HFTFeatureEngineer
from src.ml.models.goliath_transformer import GoliathTransformer, GoliathConfig

# --- PRO CONFIGURATION ---
SEQ_LEN = 64
PREDICT_HORIZON = 10     # Look further ahead (stable)
BATCH_SIZE = 128         # Bigger batch for stability
EPOCHS = 15              # More epochs with scheduler
MAX_LR = 1e-3            # Peak Learning Rate
DROPOUT = 0.2            # Higher dropout
DATA_PATH = 'data/massive_mixed_scenario.parquet'

def create_sequences(data: np.ndarray, targets: np.ndarray, seq_len: int):
    # Safer implementation than raw strides
    num_samples = len(data) - seq_len
    features = data.shape[1]
    
    # Pre-allocate memory (Much faster than appending to list)
    X = np.zeros((num_samples, seq_len, features), dtype=np.float32)
    y = np.zeros(num_samples, dtype=np.int64)
    
    for i in range(num_samples):
        X[i] = data[i : i + seq_len]
        y[i] = targets[i + seq_len - 1]
        
    return X, y

def create_dynamic_labels(df: pd.DataFrame, horizon: int = 10):
    """
    Labeling based on Dynamic Volatility Threshold.
    Target 2 (Up) if return > 1.5 * local_volatility
    """
    future_price = df['trade_price'].shift(-horizon)
    current_price = df['trade_price']
    
    # Forward Return
    returns = (future_price - current_price) / current_price
    
    # Local Volatility (Standard Deviation of last 50 ticks)
    # We use a minimum floor for volatility to avoid exploding thresholds in flat markets
    vol = df['trade_price'].pct_change().rolling(50).std()
    vol_threshold = vol * 1.5 
    vol_threshold = vol_threshold.fillna(0.0001) # Default floor
    vol_threshold = vol_threshold.replace(0, 0.0001) # Safety
    
    labels = np.ones(len(returns)) # 1 = Hold
    
    # Dynamic Thresholding
    labels[returns > vol_threshold] = 2  # Up
    labels[returns < -vol_threshold] = 0 # Down
    
    # Drop end
    return labels[:-horizon]

def main():
    logger.info("Starting Goliath HFT Training V3 (Pro)...")
    
    # 1. LOAD MASSIVE DATA
    engineer = HFTFeatureEngineer()
    if not os.path.exists(DATA_PATH):
        logger.error(f"Data not found at {DATA_PATH}. Run generate_massive.py first.")
        return

    df_raw = engineer.load_data(DATA_PATH)
    logger.info(f"Loaded {len(df_raw)} ticks. Computing features...")
    df_feat = engineer.compute_all_features(df_raw)
    
    # 2. DYNAMIC LABELING
    raw_labels = create_dynamic_labels(df_feat, horizon=PREDICT_HORIZON)
    df_feat = df_feat.iloc[:len(raw_labels)]
    
    # Features
    feature_cols = [c for c in df_feat.columns if 'feature_' in c]
    X_raw = df_feat[feature_cols].values
    y_raw = raw_labels
    
    # 3. CLASS WEIGHTING
    # Calculate weights to handle class imbalance (Hold is usually dominant)
    classes = np.unique(y_raw)
    weights = compute_class_weight(class_weight='balanced', classes=classes, y=y_raw)
    class_weights = torch.FloatTensor(weights)
    logger.info(f"Class Weights (Down, Hold, Up): {weights}")
    
    # 4. SPLIT (Walk-Forward)
    # Train on first 80%, Test on last 20% (simulating future)
    train_size = int(len(X_raw) * 0.8)
    X_train_raw, X_test_raw = X_raw[:train_size], X_raw[train_size:]
    y_train_raw, y_test_raw = y_raw[:train_size], y_raw[train_size:]
    
    # Normalize
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_raw)
    X_test_scaled = scaler.transform(X_test_raw)
    
    # 5. TENSORS
    logger.info("Building Tensors...")
    X_train, y_train = create_sequences(X_train_scaled, y_train_raw, SEQ_LEN)
    X_test, y_test = create_sequences(X_test_scaled, y_test_raw, SEQ_LEN)
    
    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train)), batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(TensorDataset(torch.FloatTensor(X_test), torch.LongTensor(y_test)), batch_size=BATCH_SIZE, shuffle=False)
    
    # 6. MODEL & OPTIMIZER
    config = GoliathConfig(
        input_dim=X_train.shape[2],
        d_model=128,
        nhead=4,
        num_layers=3,
        output_dim=3,
        dropout=DROPOUT, # High dropout
        max_seq_len=SEQ_LEN
    )
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GoliathTransformer(config).to(device)
    
    # Weighted Loss
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    
    optimizer = optim.AdamW(model.parameters(), lr=MAX_LR/10, weight_decay=1e-2)
    
    # Scheduler: OneCycleLR
    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer, 
        max_lr=MAX_LR, 
        steps_per_epoch=len(train_loader), 
        epochs=EPOCHS
    )
    
    # 7. TRAINING LOOP
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
            
            # Gradient Clipping (Stability)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            
            optimizer.step()
            scheduler.step()
            
            train_loss += loss.item()
            _, pred = torch.max(out, 1)
            total += y_b.size(0)
            correct += (pred == y_b).sum().item()
            
        train_acc = 100 * correct / total
        
        # Validation
        model.eval()
        val_correct = 0
        val_total = 0
        val_loss = 0
        
        with torch.no_grad():
            for X_b, y_b in test_loader:
                X_b, y_b = X_b.to(device), y_b.to(device)
                out = model(X_b)
                loss = criterion(out, y_b)
                val_loss += loss.item()
                _, pred = torch.max(out, 1)
                val_total += y_b.size(0)
                val_correct += (pred == y_b).sum().item()
        
        val_acc = 100 * val_correct / val_total
        
        logger.info(f"Epoch {epoch+1}/{EPOCHS} | Train Acc: {train_acc:.2f}% | Val Acc: {val_acc:.2f}% | Loss: {train_loss/len(train_loader):.4f}")
        
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), 'analysis/models_checkpoint/goliath_pro.pth')
            
    logger.success(f"Pro Training Complete. Best Val Acc: {best_acc:.2f}%")
    logger.info("Model saved to analysis/models_checkpoint/goliath_pro.pth")

if __name__ == "__main__":
    main()
