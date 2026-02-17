#!/usr/bin/env python3
"""
predict.py - Live Inference for Goliath V2
==========================================

Loads the trained model and scaler, fetches the latest market data,
and generates a prediction for the next candle.
"""

import asyncio
import os
import sys
import json
import torch
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.insert(0, os.getcwd())

from engine.model_loader import ModelLoader
from analysis.goliath_trainer_v2 import GoliathDataPipeline, TrainingConfig
from src.integration.exchange_manager import ExchangeManager
from src.integration.config import ExchangeConfig

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Goliath Live Prediction")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Symbol to predict")
    parser.add_argument("--timeframe", type=str, default="5m", help="Timeframe (must match training)")
    parser.add_argument("--model-dir", type=str, default="analysis/models_checkpoint", help="Path to checkpoints")
    parser.add_argument("--exchange", type=str, default="binance", help="Exchange ID")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds (default 300 for 5m)")
    args = parser.parse_args()

    # 1. Load Configuration
    train_config = TrainingConfig()
    
    # Locate best model and scaler
    model_path = f"{args.model_dir}/goliath_production.pth"
    scaler_path = f"{args.model_dir}/goliath_scaler.json"
    
    if not os.path.exists(model_path):
        # Fallback to finding latest checkpoint
        checkpoints = sorted(list(Path(args.model_dir).glob("goliath_v*.pth")))
        if not checkpoints:
            logger.error(f"No models found in {args.model_dir}")
            return
        model_path = str(checkpoints[-1])
        # Try to find matching scaler
        version = model_path.split('_v')[-1].split('_')[0] # Extract version
        scaler_path = f"{args.model_dir}/goliath_scaler_v{version}.json"
        
    logger.info(f"Loading model: {model_path}")
    logger.info(f"Loading scaler: {scaler_path}")
    
    if not os.path.exists(scaler_path):
        logger.error("Scaler file not found! Inference will be garbage.")
        return

    # 2. Initialize Model Loader
    device = "cuda" if torch.cuda.is_available() else "cpu"
    loader = ModelLoader(model_path, scaler_path, device=device)
    loader.load()
    
    # 3. Setup Loop
    while True:
        try:
            # Fetch Live Data
            ex_config = ExchangeConfig(exchange_id=args.exchange, sandbox=False)
            exchange = ExchangeManager(ex_config)
            
            logger.info(f"Fetching recent data for {args.symbol}...")
            
            # We need enough data for feature engineering (window=50) + sequence (64)
            # 200 candles should be safe
            df = await exchange.fetch_ohlcv(args.symbol, timeframe=args.timeframe, limit=200)
            await exchange.close()
            
            if len(df) < 100:
                logger.error(f"Not enough data received: {len(df)} rows")
                if not args.loop: break
                await asyncio.sleep(60)
                continue
                
            # Convert Decimal to float for ML
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                df[col] = df[col].astype(float)
                
            # Convert nanoseconds timestamp to datetime
            df['date'] = pd.to_datetime(df['timestamp'], unit='ns')
            df.set_index('date', inplace=True)
                
            # 4. Feature Engineering
            # We reuse the pipeline logic for consistency (parity!)
            pipeline = GoliathDataPipeline(train_config)
            
            # Trick: Use the loaded scaler for the pipeline too, or manually scale
            # Pipeline.engineer_features returns df with feature columns
            try:
                df_features = pipeline.engineer_features(df)
            except Exception as e:
                logger.error(f"Feature engineering failed: {e}")
                if not args.loop: break
                await asyncio.sleep(60)
                continue
        
            logger.info(f"Generated features: {len(df_features)} rows")
            
            # 5. Prepare Sequence
            # We need the LAST sequence_length rows
            seq_len = train_config.sequence_length
            
            if len(df_features) < seq_len:
                logger.error("Not enough data after feature engineering")
                if not args.loop: break
                await asyncio.sleep(60)
                continue
                
            # Extract feature columns
            # We blindly trust the pipeline's extraction logic matches training
            last_sequence_df = df_features[pipeline.feature_cols].tail(seq_len)
            raw_sequence = last_sequence_df.values
            
            # 6. Predict
            # ModelLoader handles scaling internally using the loaded scaler
            # So we pass RAW sequence
            prediction = loader.predict(raw_sequence)
            
            # 7. Output
            print("\n" + "="*40)
            print(f"🔮 PREDICTION: {args.symbol} ({args.timeframe})")
            print(f"   Timestamp:  {df.index[-1]}")
            print(f"   Action:     {['SELL', 'HOLD', 'BUY'][prediction['action']]}")
            print(f"   Confidence: {prediction['confidence']:.2%}")
            print(f"   TP/SL Mult: {prediction['tp_sl']}")
            print("="*40 + "\n")
        
            # Log specific probabilities if available
            if 'logits' in prediction:
                probs = torch.softmax(torch.tensor(prediction['logits']), dim=0)
                logger.info(f"Probabilities: Sell={probs[0]:.2f}, Hold={probs[1]:.2f}, Buy={probs[2]:.2f}")

        except Exception as e:
            logger.error(f"Prediction loop error: {e}")
            
        if not args.loop:
            break
            
        logger.info(f"Sleeping for {args.interval} seconds...")
        import asyncio
        await asyncio.sleep(args.interval)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
