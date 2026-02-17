#!/usr/bin/env python3
"""
Train CPU-only models (LightGBM + XGBoost) in parallel with GPU training.

Uses the same GoliathDataPipeline for consistency, then flattens sequences
into tabular format for tree-based models.

Usage:
    python scripts/train_cpu_models.py
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

import numpy as np
from loguru import logger

# Project imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from analysis.goliath_trainer_v2 import TrainingConfig, GoliathDataPipeline
from analysis.src.ml.models.model_zoo import get_model


CHECKPOINT_DIR = PROJECT_ROOT / "analysis" / "models_checkpoint"


def train_tree_models():
    """Train LightGBM and XGBoost on CPU."""
    start = time.time()
    logger.info("=" * 60)
    logger.info("TRAINING CPU — Modelli ad Albero (LightGBM + XGBoost)")
    logger.info("=" * 60)

    # --- Data pipeline (same as GPU trainer) ---
    config = TrainingConfig()
    config.device = "cpu"
    pipeline = GoliathDataPipeline(config)

    logger.info("Caricamento dati...")
    df = pipeline.load_all_data()
    df = pipeline.engineer_features(df)
    labels = pipeline.create_labels(df)
    X_seq, y = pipeline.create_sequences(df, labels)

    # Flatten sequences (N, 64, feat) -> (N, 64*feat) for tabular models
    n_samples, seq_len, n_feat = X_seq.shape
    X_flat = X_seq.reshape(n_samples, seq_len * n_feat)
    logger.info(f"Dati: {n_samples:,} campioni, {X_flat.shape[1]} feature (appiattite)")

    # Train/test split (80/20, time-ordered)
    split_idx = int(n_samples * 0.8)
    X_train, X_test = X_flat[:split_idx], X_flat[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    results = {}

    # --- LightGBM ---
    logger.info("-" * 40)
    logger.info("Training LightGBM...")
    try:
        lgbm = get_model("lightgbm", n_estimators=300, num_leaves=63, learning_rate=0.05)
        lgbm.fit(X_train, y_train)
        preds, confs = lgbm.predict(X_test)
        acc = (preds == y_test).mean() * 100
        results["lightgbm"] = {"accuracy": round(acc, 2), "status": "OK"}
        logger.success(f"LightGBM — Accuratezza: {acc:.2f}%")

        lgbm.save(str(CHECKPOINT_DIR / "lightgbm_latest.joblib"))
        logger.info(f"Salvato: {CHECKPOINT_DIR / 'lightgbm_latest.joblib'}")
    except Exception as e:
        logger.error(f"LightGBM fallito: {e}")
        results["lightgbm"] = {"accuracy": 0, "status": f"ERRORE: {e}"}

    # --- XGBoost ---
    logger.info("-" * 40)
    logger.info("Training XGBoost...")
    try:
        xgb = get_model("xgboost", n_estimators=300, max_depth=8, learning_rate=0.05)
        xgb.fit(X_train, y_train)
        preds, confs = xgb.predict(X_test)
        acc = (preds == y_test).mean() * 100
        results["xgboost"] = {"accuracy": round(acc, 2), "status": "OK"}
        logger.success(f"XGBoost — Accuratezza: {acc:.2f}%")

        xgb.save(str(CHECKPOINT_DIR / "xgboost_latest.joblib"))
        logger.info(f"Salvato: {CHECKPOINT_DIR / 'xgboost_latest.joblib'}")
    except Exception as e:
        logger.error(f"XGBoost fallito: {e}")
        results["xgboost"] = {"accuracy": 0, "status": f"ERRORE: {e}"}

    elapsed = time.time() - start

    # Save results summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "n_train": split_idx,
        "n_test": n_samples - split_idx,
        "n_features": X_flat.shape[1],
        "models": results,
    }
    summary_path = CHECKPOINT_DIR / "cpu_training_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("=" * 60)
    logger.info(f"TRAINING CPU COMPLETATO in {elapsed:.0f}s")
    for name, res in results.items():
        logger.info(f"  {name:12s} — Acc: {res['accuracy']:.2f}%  [{res['status']}]")
    logger.info("=" * 60)


if __name__ == "__main__":
    train_tree_models()
