#!/usr/bin/env python3
"""
GOLIATH XAU/USD Long-Term Trainer
=================================
Specialized trainer for Gold Daily Data.
Target: 5-day horizon (Weekly trend).
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from loguru import logger
import torch

# Import core components from Goliath v2
from analysis.goliath_trainer_v2 import (
    GoliathTrainer, 
    GoliathDataPipeline, 
    TrainingConfig, 
    detect_gpu
)

# Customize Configuration for Long Term XAU
@dataclass
class XAUConfig(TrainingConfig):
    # Specialized overriding
    sequence_length: int = 60       # 60 Days (~3 months context)
    batch_size: int = 128           # Larger batch for stable gradients
    learning_rate: float = 5e-5     # Lower learning rate for fine-tuning
    epochs_per_session: int = 100   # Longer sessions
    
    # Model Capacity
    d_model: int = 512              # Increased capacity
    num_layers: int = 8             # Deeper network
    dropout: float = 0.3            # Higher dropout for regularization
    
    # Target
    target_accuracy: float = 0.80   # Ambitious target
    min_confidence: float = 0.70
    
    # Data
    data_dir: str = "data"          # Filter specifically for xau*
    
    def __post_init__(self):
        # Ensure directories exist
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.tensorboard_dir, exist_ok=True)

class XAUPipeline(GoliathDataPipeline):
    """Specialized pipeline for XAU data."""
    
    def load_all_data(self):
        """Load ONLY xau_usd_daily.parquet."""
        file_path = f"{self.config.data_dir}/xau_usd_daily.parquet"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing {file_path}. Run fetch_xau_data.py first.")
            
        logger.info(f"Loading XAU data: {file_path}")
        import pandas as pd
        df = pd.read_parquet(file_path)
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df

    def engineer_features(self, df):
        """Advanced Feature Engineering using pandas_ta."""
        logger.info("Engineering Advanced XAU Features...")
        
        try:
            import pandas_ta as ta
        except ImportError:
            logger.warning("pandas_ta not found! Installing...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas_ta"])
            import pandas_ta as ta

        # Ensure datetime index for some ta libs if needed, but pandas_ta usually handles columns
        # We work on a copy
        df = df.copy()
        
        # 1. Trend Indicators
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.macd(append=True)
        df.ta.adx(append=True)
        
        # 2. Momentum
        df.ta.rsi(length=14, append=True)
        df.ta.rsi(length=28, append=True) # Long term RSI
        df.ta.stoch(append=True)
        df.ta.cci(append=True)
        
        # 3. Volatility
        df.ta.bbands(length=20, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.kc(append=True) # Keltner Channels
        
        # 4. Volume
        df.ta.obv(append=True)
        df.ta.mfi(append=True)
        
        # 5. Custom Log Returns
        import numpy as np
        df['log_ret'] = np.log(df['close']) - np.log(df['close'].shift(1))
        df['log_ret_5'] = np.log(df['close']) - np.log(df['close'].shift(5))
        
        # Clean up
        self.feature_cols = [c for c in df.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # Add basic price/vol norms if not present
        # (Usually better to let the scaler handle normalization, but ratios are good)
        df['close_div_ema50'] = df['close'] / df['EMA_50']
        self.feature_cols.append('close_div_ema50')
        
        # Drop NaN from indicator warmup
        df = df.dropna()
        
        logger.info(f"Generated {len(self.feature_cols)} features: {self.feature_cols}")
        return df

    def create_labels(self, df, horizon=5):
        """Override label creation for 5-day horizon."""
        logger.info(f"Creating labels with horizon={horizon} days...")
        return super().create_labels(df, horizon=horizon)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="GOLIATH XAU Trainer")
    parser.add_argument("--mode", choices=["train", "test"], default="train", help="Mode")
    args = parser.parse_args()
    
    # 1. Config
    config = XAUConfig()
    
    # 2. Pipeline
    logger.info("Initializing XAU Pipeline...")
    pipeline = XAUPipeline(config)
    
    # 3. Load & Process
    df = pipeline.load_all_data()
    df = pipeline.engineer_features(df)
    
    # 4. Create sequences (Horizon = 5 days)
    labels = pipeline.create_labels(df, horizon=5)
    X, y = pipeline.create_sequences(df, labels)
    
    # 5. Dataloaders
    train_dl, val_dl, test_dl = pipeline.prepare_dataloaders(X, y)
    
    # 6. Trainer
    trainer = GoliathTrainer(config)
    trainer.initialize_model(input_dim=len(pipeline.feature_cols))
    trainer.register_scaler(pipeline.scaler)
    
    logger.info(f"Start Training on {trainer.device} ({trainer.gpu_name})")
    
    if args.mode == "test":
        config.epochs_per_session = 2
        trainer.run_training_session(train_dl, val_dl)
    else:
        # Loop
        session = 0
        while True:
            acc = trainer.run_training_session(train_dl, val_dl, session)
            session += 1
            if acc >= config.target_accuracy * 100:
                logger.success("Target Accuracy Reached!")
                break

if __name__ == "__main__":
    main()
