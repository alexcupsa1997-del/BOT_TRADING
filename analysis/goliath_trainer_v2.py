#!/usr/bin/env python3
"""
GOLIATH Continuous Learning Engine v2.0
========================================
Advanced training system with AMD ROCm support for Radeon 9070XT.

Features:
- ROCm/CUDA auto-detection
- Mixed Precision training (FP16)
- Multi-source data integration
- TensorBoard logging
- Model versioning & promotion
- 1-week intensive training mode

Usage:
    python analysis/goliath_trainer_v2.py --mode=week   # Full week training
    python analysis/goliath_trainer_v2.py --mode=continuous  # 24/7 daemon
"""

import os
import sys
import time
import glob
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, random_split
from torch.utils.tensorboard import SummaryWriter
from sklearn.preprocessing import StandardScaler
from loguru import logger

# Project imports
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add project root
from engine.models.goliath import GoliathTransformerV2
from analysis.src.quant.hft_features import HFTFeatureEngineer
from analysis.src.quant.indicators import compute_all_indicators
from analysis.src.quant.patterns import detect_all_patterns

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TrainingConfig:
    """Training configuration for intensive learning."""
    
    # Hardware
    device: str = "auto"  # auto, cuda, rocm, cpu
    mixed_precision: bool = True
    num_workers: int = 4
    
    # Model Architecture
    d_model: int = 256
    nhead: int = 8
    num_layers: int = 6
    dropout: float = 0.2
    sequence_length: int = 64
    
    # Training Hyperparameters
    batch_size: int = 256
    learning_rate: float = 3e-4
    min_lr: float = 1e-6
    weight_decay: float = 0.01
    gradient_accumulation: int = 4
    
    # Week-long Training
    epochs_per_session: int = 100
    sessions_per_day: int = 24  # Every hour
    total_days: int = 7
    
    # Model Management
    checkpoint_dir: str = "analysis/models_checkpoint"
    tensorboard_dir: str = "analysis/runs"
    
    # Target
    target_accuracy: float = 0.80
    min_confidence: float = 0.75
    
    # Data
    data_dir: str = "data"
    train_split: float = 0.8
    val_split: float = 0.1
    test_split: float = 0.1


# =============================================================================
# GPU DETECTION (ROCm/CUDA)
# =============================================================================

def detect_gpu() -> Tuple[torch.device, bool, str]:
    """
    Detect available GPU (ROCm for AMD, CUDA for NVIDIA).
    
    Returns:
        (device, has_gpu, gpu_name)
    """
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        
        # Check if ROCm (AMD) or CUDA (NVIDIA)
        if "AMD" in gpu_name or "Radeon" in gpu_name:
            backend = "ROCm"
        else:
            backend = "CUDA"
            
        logger.success(f"GPU Detected: {gpu_name} ({backend})")
        logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        return device, True, gpu_name
    
    logger.warning("No GPU detected. Training will be slow.")
    return torch.device("cpu"), False, "CPU"


# =============================================================================
# DATA PIPELINE
# =============================================================================

class GoliathDataPipeline:
    """Unified data pipeline for all sources."""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.engineer = HFTFeatureEngineer()
        self.scaler = StandardScaler()
        self.feature_cols: List[str] = []
        
    def load_all_data(self) -> pd.DataFrame:
        """Load and combine all parquet files."""
        files = glob.glob(f"{self.config.data_dir}/*.parquet")
        
        if not files:
            raise FileNotFoundError(f"No data files in {self.config.data_dir}")
            
        logger.info(f"Loading {len(files)} data files...")
        
        dfs = []
        for f in files:
            try:
                # Skip empty files
                if os.path.getsize(f) < 100:
                    logger.warning(f"Skipping empty file: {f}")
                    continue
                    
                df = pd.read_parquet(f)
                
                # Normalize timestamp column
                if 'timestamp' in df.columns:
                    # Convert to datetime if int (nanoseconds)
                    if df['timestamp'].dtype in ['int64', 'int32']:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ns')
                    elif df['timestamp'].dtype == 'object':
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to load {f}: {e}")
                
        if not dfs:
            raise FileNotFoundError("No valid data files could be loaded")
            
        combined = pd.concat(dfs, ignore_index=True)
        
        # Ensure timestamp is datetime for proper sorting
        if 'timestamp' in combined.columns:
            combined['timestamp'] = pd.to_datetime(combined['timestamp'], errors='coerce')
            combined = combined.dropna(subset=['timestamp'])
            combined = combined.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Loaded {len(combined):,} total records")
        return combined
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all feature engineering with robust error handling."""
        logger.info("Engineering features...")
        
        # Required columns for HFT features
        hft_cols = ['trade_price', 'bid_price', 'ask_price', 'bid_size', 'ask_size', 'volume']
        has_hft = all(c in df.columns for c in hft_cols)
        
        if has_hft:
            try:
                # HFT features (OBI, spread, volatility)
                df = self.engineer.compute_all_features(df)
            except Exception as e:
                logger.warning(f"HFT features failed: {e}. Creating basic features.")
                has_hft = False
        
        if not has_hft:
            # Fallback: create basic features from available columns
            logger.info("Creating basic features...")
            
            # Find price column
            price_col = None
            for col in ['trade_price', 'close', 'price', 'Close']:
                if col in df.columns:
                    price_col = col
                    break
                    
            if price_col is None:
                raise ValueError(f"No price column found in: {df.columns.tolist()}")
            
            # Basic features
            df['feature_log_ret'] = np.log(df[price_col]) - np.log(df[price_col].shift(1))
            df['feature_vol_10'] = df['feature_log_ret'].rolling(10).std()
            df['feature_vol_50'] = df['feature_log_ret'].rolling(50).std()
            df['feature_mom_10'] = df['feature_log_ret'].rolling(10).sum()
            df['feature_mom_50'] = df['feature_log_ret'].rolling(50).sum()
            
            # RSI
            delta = df[price_col].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 1)
            df['feature_rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            ema12 = df[price_col].ewm(span=12, adjust=False).mean()
            ema26 = df[price_col].ewm(span=26, adjust=False).mean()
            df['feature_macd'] = ema12 - ema26
            df['feature_macd_signal'] = df['feature_macd'].ewm(span=9, adjust=False).mean()
        
        # Store feature columns
        self.feature_cols = [c for c in df.columns if 'feature_' in c]
        
        if not self.feature_cols:
            raise ValueError("No features generated!")
        
        logger.info(f"Engineered {len(self.feature_cols)} features: {self.feature_cols}")
        
        # Drop rows with NaN in features (from rolling windows)
        df = df.dropna(subset=self.feature_cols)
        logger.info(f"Data after dropna: {len(df):,} rows")
        
        return df
    
    def create_labels(self, df: pd.DataFrame, horizon: int = 10) -> np.ndarray:
        """
        Create labels using dynamic thresholding.
        
        Labels:
        - 0: Sell (price drops > threshold)
        - 1: Hold (price within threshold)
        - 2: Buy (price rises > threshold)
        """
        price_col = 'trade_price' if 'trade_price' in df.columns else 'close'
        
        # Future returns
        future_price = df[price_col].shift(-horizon)
        returns = (future_price - df[price_col]) / df[price_col]
        
        # Dynamic threshold based on volatility
        vol = df[price_col].pct_change().rolling(50).std().fillna(0.001)
        threshold = vol * 1.5
        
        # Vectorized labeling
        labels = np.ones(len(df), dtype=np.int64)  # Default: Hold
        labels[returns > threshold.values] = 2     # Buy
        labels[returns < -threshold.values] = 0    # Sell
        
        return labels[:-horizon]
    
    def create_sequences(
        self, 
        df: pd.DataFrame, 
        labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for training."""
        seq_len = self.config.sequence_length
        
        # Get features and ensure no NaN
        feature_df = df[self.feature_cols].copy()
        
        # Fill NaN with 0 (after rolling windows, start has NaN)
        feature_df = feature_df.fillna(0)
        
        # Replace inf with large values
        feature_df = feature_df.replace([np.inf, -np.inf], 0)
        
        X_raw = feature_df.values[:len(labels)]  # Align with labels
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X_raw)
        
        # Replace any remaining NaN after scaling (shouldn't happen but safety)
        X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Create sequences
        num_samples = len(X_scaled) - seq_len
        if num_samples <= 0:
            raise ValueError(f"Not enough data: {len(X_scaled)} rows, need > {seq_len}")
            
        X = np.zeros((num_samples, seq_len, len(self.feature_cols)), dtype=np.float32)
        y = np.zeros(num_samples, dtype=np.int64)
        
        for i in range(num_samples):
            X[i] = X_scaled[i:i+seq_len]
            y[i] = labels[i + seq_len - 1]
            
        logger.info(f"Created {num_samples:,} sequences")
        return X, y
    
    def prepare_dataloaders(
        self, 
        X: np.ndarray, 
        y: np.ndarray
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """Create train/val/test dataloaders."""
        dataset = TensorDataset(torch.FloatTensor(X), torch.LongTensor(y))
        
        # Split sizes
        train_size = int(len(dataset) * self.config.train_split)
        val_size = int(len(dataset) * self.config.val_split)
        test_size = len(dataset) - train_size - val_size
        
        train_ds, val_ds, test_ds = random_split(
            dataset, [train_size, val_size, test_size]
        )
        
        train_loader = DataLoader(
            train_ds, 
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=self.config.num_workers,
            pin_memory=True
        )
        
        val_loader = DataLoader(
            val_ds,
            batch_size=self.config.batch_size,
            num_workers=self.config.num_workers,
            pin_memory=True
        )
        
        test_loader = DataLoader(
            test_ds,
            batch_size=self.config.batch_size,
            num_workers=self.config.num_workers,
            pin_memory=True
        )
        
        return train_loader, val_loader, test_loader


# =============================================================================
# TRAINING ENGINE
# =============================================================================

class GoliathTrainer:
    """Advanced training engine with all optimizations."""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.device, self.has_gpu, self.gpu_name = detect_gpu()
        
        # Model & Optimizer
        self.model: Optional[GoliathTransformerV2] = None
        self.optimizer: Optional[optim.AdamW] = None
        self.scheduler: Optional[optim.lr_scheduler.OneCycleLR] = None
        self.scaler: Optional[StandardScaler] = None # This is for feature scaling, not GradScaler
        
        # Mixed precision (GradScaler)
        self.grad_scaler = torch.cuda.amp.GradScaler() if (
            self.has_gpu and config.mixed_precision
        ) else None
        
        # State
        self.best_accuracy = 0.0
        self.best_model_path = ""
        self.training_start = datetime.now()
        
        # Logging
        os.makedirs(config.checkpoint_dir, exist_ok=True)
        self.writer = SummaryWriter(
            log_dir=f"{config.tensorboard_dir}/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Checkpoints
        os.makedirs(config.checkpoint_dir, exist_ok=True)

    def register_scaler(self, scaler: StandardScaler):
        """Register scaler for saving."""
        self.scaler = scaler
        
    def initialize_model(self, input_dim: int):
        """Initialize or load model."""
        self.model = GoliathTransformerV2(self.config, input_dim).to(self.device)
        
        # Try to load existing best model
        production_path = f"{self.config.checkpoint_dir}/goliath_production.pth"
        if os.path.exists(production_path):
            try:
                self.model.load_state_dict(
                    torch.load(production_path, map_location=self.device)
                )
                logger.info("Loaded existing production model for fine-tuning")
            except Exception as e:
                logger.warning(f"Could not load model: {e}. Starting fresh.")
        
        # Optimizer with weight decay
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        
        # Cosine annealing scheduler
        self.scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer,
            T_0=10,
            T_mult=2,
            eta_min=self.config.min_lr
        )
        
        # Log model size
        params = sum(p.numel() for p in self.model.parameters())
        logger.info(f"Model initialized: {params:,} parameters")
        
    def train_epoch(
        self, 
        train_loader: DataLoader,
        epoch: int
    ) -> Tuple[float, float]:
        """Train for one epoch with gradient accumulation."""
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        
        criterion = nn.CrossEntropyLoss()
        accumulation_steps = self.config.gradient_accumulation
        
        self.optimizer.zero_grad()
        
        for batch_idx, (X, y) in enumerate(train_loader):
            X, y = X.to(self.device), y.to(self.device)
            
            # Mixed precision forward
            if self.grad_scaler:
                with torch.cuda.amp.autocast():
                    outputs = self.model(X)
                    loss = criterion(outputs['direction'], y)
                    loss = loss / accumulation_steps
                    
                self.grad_scaler.scale(loss).backward()
                
                if (batch_idx + 1) % accumulation_steps == 0:
                    self.grad_scaler.step(self.optimizer)
                    self.grad_scaler.update()
                    self.optimizer.zero_grad()
            else:
                outputs = self.model(X)
                loss = criterion(outputs['direction'], y)
                loss = loss / accumulation_steps
                loss.backward()
                
                if (batch_idx + 1) % accumulation_steps == 0:
                    self.optimizer.step()
                    self.optimizer.zero_grad()
            
            total_loss += loss.item() * accumulation_steps
            
            # Accuracy
            _, predicted = torch.max(outputs['direction'], 1)
            total += y.size(0)
            correct += (predicted == y).sum().item()
            
        return total_loss / len(train_loader), 100 * correct / total
    
    def validate(self, val_loader: DataLoader) -> Tuple[float, float, float]:
        """Validate model."""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        high_conf_correct = 0
        high_conf_total = 0
        total = 0
        
        criterion = nn.CrossEntropyLoss()
        
        with torch.no_grad():
            for X, y in val_loader:
                X, y = X.to(self.device), y.to(self.device)
                
                if self.grad_scaler:
                    with torch.cuda.amp.autocast():
                        outputs = self.model(X)
                        loss = criterion(outputs['direction'], y)
                else:
                    outputs = self.model(X)
                    loss = criterion(outputs['direction'], y)
                    
                total_loss += loss.item()
                
                _, predicted = torch.max(outputs['direction'], 1)
                confidence = outputs['confidence']
                
                total += y.size(0)
                correct += (predicted == y).sum().item()
                
                # High confidence predictions
                high_conf_mask = confidence > self.config.min_confidence
                if high_conf_mask.sum() > 0:
                    high_conf_total += high_conf_mask.sum().item()
                    high_conf_correct += (
                        (predicted == y) & high_conf_mask
                    ).sum().item()
                    
        accuracy = 100 * correct / total
        high_conf_acc = (
            100 * high_conf_correct / high_conf_total 
            if high_conf_total > 0 else 0
        )
        
        return total_loss / len(val_loader), accuracy, high_conf_acc
    
    def save_checkpoint(self, accuracy: float, epoch: int):
        """Save model checkpoint."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"goliath_v{epoch}_{accuracy:.1f}pct_{timestamp}.pth"
        path = f"{self.config.checkpoint_dir}/{filename}"
        
        torch.save(self.model.state_dict(), path)
        logger.info(f"Saved checkpoint: {filename}")
        
        # Save Scaler
        if self.scaler:
            scaler_path = f"{self.config.checkpoint_dir}/goliath_scaler_v{epoch}.json"
            with open(scaler_path, 'w') as f:
                json.dump({
                    'mean': self.scaler.mean_.tolist(),
                    'scale': self.scaler.scale_.tolist()
                }, f)
            logger.info(f"Saved scaler: {scaler_path}")
            
            # Update production scaler
            if accuracy > self.best_accuracy:
                prod_scaler_path = f"{self.config.checkpoint_dir}/goliath_scaler.json"
                shutil.copy(scaler_path, prod_scaler_path)
        
        # Update production model if best
        if accuracy > self.best_accuracy:
            self.best_accuracy = accuracy
            self.best_model_path = path
            
            production_path = f"{self.config.checkpoint_dir}/goliath_production.pth"
            shutil.copy(path, production_path)
            logger.success(f"🏆 New best model: {accuracy:.2f}% accuracy")
            
    def run_training_session(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        session_id: int = 0
    ) -> float:
        """Run a full training session."""
        logger.info(f"Starting training session {session_id}")
        
        best_val_acc = 0.0
        
        for epoch in range(self.config.epochs_per_session):
            # Train
            train_loss, train_acc = self.train_epoch(train_loader, epoch)
            
            # Validate
            val_loss, val_acc, high_conf_acc = self.validate(val_loader)
            
            # Update scheduler
            self.scheduler.step()
            
            # Log to TensorBoard
            global_step = session_id * self.config.epochs_per_session + epoch
            self.writer.add_scalar('Loss/train', train_loss, global_step)
            self.writer.add_scalar('Loss/val', val_loss, global_step)
            self.writer.add_scalar('Accuracy/train', train_acc, global_step)
            self.writer.add_scalar('Accuracy/val', val_acc, global_step)
            self.writer.add_scalar('Accuracy/high_conf', high_conf_acc, global_step)
            self.writer.add_scalar('LR', self.optimizer.param_groups[0]['lr'], global_step)
            
            # Log progress
            if epoch % 10 == 0:
                logger.info(
                    f"  Epoch {epoch:3d} | "
                    f"Train: {train_acc:.1f}% | "
                    f"Val: {val_acc:.1f}% | "
                    f"HighConf: {high_conf_acc:.1f}%"
                )
                
            # Save if improved
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                self.save_checkpoint(val_acc, global_step)
                
        return best_val_acc
    
    def run_week_training(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        test_loader: DataLoader
    ):
        """Run 1-week intensive training."""
        self.training_start = datetime.now()
        end_time = self.training_start + timedelta(days=self.config.total_days)
        
        logger.info("=" * 60)
        logger.info("🚀 GOLIATH 1-WEEK INTENSIVE TRAINING STARTED")
        logger.info(f"   GPU: {self.gpu_name}")
        logger.info(f"   Start: {self.training_start}")
        logger.info(f"   End:   {end_time}")
        logger.info(f"   Target: {self.config.target_accuracy * 100:.0f}% accuracy")
        logger.info("=" * 60)
        
        session_id = 0
        
        while datetime.now() < end_time:
            # Run training session
            session_acc = self.run_training_session(
                train_loader, val_loader, session_id
            )
            
            # Check if target reached
            if self.best_accuracy >= self.config.target_accuracy * 100:
                logger.success(
                    f"🎯 TARGET REACHED! {self.best_accuracy:.2f}% accuracy"
                )
                break
                
            # Progress report
            elapsed = datetime.now() - self.training_start
            remaining = end_time - datetime.now()
            
            logger.info(
                f"📊 Session {session_id} complete | "
                f"Best: {self.best_accuracy:.1f}% | "
                f"Elapsed: {elapsed} | "
                f"Remaining: {remaining}"
            )
            
            session_id += 1
            
            # Brief pause between sessions
            time.sleep(60)
            
        # Final evaluation on test set
        logger.info("Running final evaluation on test set...")
        test_loss, test_acc, test_high_conf = self.validate(test_loader)
        
        logger.info("=" * 60)
        logger.info("🏁 TRAINING COMPLETE")
        logger.info(f"   Best Accuracy: {self.best_accuracy:.2f}%")
        logger.info(f"   Test Accuracy: {test_acc:.2f}%")
        logger.info(f"   High Conf Acc: {test_high_conf:.2f}%")
        logger.info(f"   Best Model: {self.best_model_path}")
        logger.info("=" * 60)
        
        self.writer.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="GOLIATH Trainer v2")
    parser.add_argument(
        "--mode", 
        choices=["week", "continuous", "test"],
        default="week",
        help="Training mode"
    )
    args = parser.parse_args()
    
    # Configuration
    config = TrainingConfig()
    
    # Data pipeline
    logger.info("Initializing data pipeline...")
    pipeline = GoliathDataPipeline(config)
    
    # Load and process data
    df = pipeline.load_all_data()
    df = pipeline.engineer_features(df)
    
    # Create labels and sequences
    labels = pipeline.create_labels(df)
    X, y = pipeline.create_sequences(df, labels)
    
    # Create dataloaders
    train_loader, val_loader, test_loader = pipeline.prepare_dataloaders(X, y)
    
    # Initialize trainer
    trainer = GoliathTrainer(config)
    trainer.initialize_model(input_dim=len(pipeline.feature_cols))
    trainer.register_scaler(pipeline.scaler)
    
    # Run training
    if args.mode == "week":
        trainer.run_week_training(train_loader, val_loader, test_loader)
    elif args.mode == "test":
        # Quick test run
        config.epochs_per_session = 5
        trainer.run_training_session(train_loader, val_loader)
    else:
        # Continuous mode - infinite loop
        session_id = 0
        while True:
            trainer.run_training_session(train_loader, val_loader, session_id)
            session_id += 1
            time.sleep(300)  # 5 min pause


if __name__ == "__main__":
    main()
