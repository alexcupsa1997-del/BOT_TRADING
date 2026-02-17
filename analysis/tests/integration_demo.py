#!/usr/bin/env python3
"""
GOLIATH v2.0 — Integration Demo (Terminal Test)

Full pipeline test:
  1. Load synthetic market data
  2. Compute indicators + features
  3. Triple Barrier labeling
  4. Backtest with trend-following strategy
  5. Walk-Forward fold generation
  6. Model Zoo: train & predict with all models
  7. Ensemble: stack predictions
  8. Hyperopt: quick 5-trial optimization

Usage:
    PYTHONPATH=. python analysis/tests/integration_demo.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO",
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <level>{message}</level>")


def sep(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    t0 = time.time()

    # =========================================================================
    # 1. LOAD DATA
    # =========================================================================
    sep("1. LOADING SYNTHETIC MARKET DATA")

    data_path = Path(__file__).parent.parent / "data" / "synthetic_market.parquet"
    if not data_path.exists():
        logger.error(f"Data not found: {data_path}")
        logger.info("Run: PYTHONPATH=. python analysis/generate_data.py")
        sys.exit(1)

    raw = pd.read_parquet(data_path)
    logger.info(f"Loaded {len(raw):,} rows from {data_path.name}")

    # Convert to OHLCV if needed
    if "timestamp" in raw.columns:
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit="ms")
        raw = raw.set_index("timestamp")

    if "close" not in raw.columns and "price" in raw.columns:
        price_col = "price"
    elif "close" in raw.columns:
        price_col = "close"
    elif "bid" in raw.columns:
        raw["price"] = (raw["bid"] + raw["ask"]) / 2
        price_col = "price"
    else:
        logger.error(f"No price column found. Columns: {list(raw.columns)}")
        sys.exit(1)

    # Resample to 1H for faster processing
    ohlcv = raw[price_col].resample("1h").agg(["first", "max", "min", "last"])
    ohlcv.columns = ["open", "high", "low", "close"]
    if "volume" in raw.columns:
        ohlcv["volume"] = raw["volume"].resample("1h").sum()
    else:
        ohlcv["volume"] = 100.0
    ohlcv = ohlcv.dropna()
    logger.info(f"Resampled to 1H: {len(ohlcv):,} bars, "
                f"range {ohlcv.index[0].date()} → {ohlcv.index[-1].date()}")
    logger.info(f"Price range: {ohlcv['close'].min():.2f} → {ohlcv['close'].max():.2f}")

    # =========================================================================
    # 2. INDICATORS + FEATURES
    # =========================================================================
    sep("2. COMPUTING INDICATORS & FEATURES")

    from src.quant.indicators import compute_all_indicators
    from src.quant.features import fractional_differencing, triple_barrier_labels

    df = compute_all_indicators(ohlcv)
    indicator_count = len([c for c in df.columns if c not in ohlcv.columns])
    logger.info(f"Computed {indicator_count} indicators")

    df["close_fracdiff"] = fractional_differencing(df["close"], d=0.4)
    logger.info("Applied fractional differencing (d=0.4)")

    # =========================================================================
    # 3. TRIPLE BARRIER LABELING
    # =========================================================================
    sep("3. TRIPLE BARRIER LABELING")

    from src.quant.triple_barrier import TripleBarrier

    tb = TripleBarrier(sl_pct=0.02, tp_pct=0.03, max_bars=48)
    labels = tb.label_series(df, side=1)
    valid = labels.dropna()
    wins = (valid == 1).sum()
    losses = (valid == -1).sum()
    timeouts = (valid == 0).sum()
    logger.info(f"Labels: +1(TP)={wins}, -1(SL)={losses}, 0(timeout)={timeouts}")
    logger.info(f"Win rate from labels: {wins / max(wins + losses, 1):.1%}")

    # =========================================================================
    # 4. BACKTEST
    # =========================================================================
    sep("4. BACKTESTING — SMA Crossover Strategy")

    from decimal import Decimal
    from src.quant.backtest_engine import BacktestEngine, BacktestConfig, Strategy
    from typing import Optional, Dict, Any

    class SMACrossover(Strategy):
        def __init__(self, fast=10, slow=30):
            self.fast = fast
            self.slow = slow

        def on_candle(self, idx, row, history) -> Optional[Dict[str, Any]]:
            if idx < self.slow + 1:
                return None
            fast_sma = history["close"].iloc[-self.fast:].mean()
            slow_sma = history["close"].iloc[-self.slow:].mean()
            prev_fast = history["close"].iloc[-self.fast - 1:-1].mean()
            prev_slow = history["close"].iloc[-self.slow - 1:-1].mean()

            if prev_fast <= prev_slow and fast_sma > slow_sma:
                return {"direction": "LONG", "tag": "sma_cross_up"}
            if prev_fast >= prev_slow and fast_sma < slow_sma:
                return {"direction": "SHORT", "tag": "sma_cross_down"}
            return None

    engine = BacktestEngine()
    config = BacktestConfig(
        initial_capital=Decimal("10000"),
        commission_pct=Decimal("0.001"),
        sl_pct=0.02, tp_pct=0.03, max_bars=48,
        seed=42,
    )
    result = engine.run(df, SMACrossover(), config)
    print(engine.format_report(result.metrics))

    # =========================================================================
    # 5. WALK-FORWARD VALIDATION
    # =========================================================================
    sep("5. WALK-FORWARD FOLD GENERATION")

    from src.ml.training.walk_forward import WalkForwardValidator

    wf = WalkForwardValidator(train_days=30, test_days=10, purge_days=1, min_train_samples=100)
    folds = wf.generate_folds(df)
    logger.info(f"Generated {len(folds)} walk-forward folds")
    for f in folds[:5]:
        logger.info(f"  Fold {f.fold_id}: train {len(f.train_indices)} bars → "
                     f"test {len(f.test_indices)} bars")

    # =========================================================================
    # 6. MODEL ZOO — Train & Predict
    # =========================================================================
    sep("6. MODEL ZOO — Training All Models")

    from src.ml.models.model_zoo import MODEL_REGISTRY, get_model

    # Prepare ML features: use last N bars of indicator data
    feature_cols = ["rsi", "adx", "atr", "cci", "close_fracdiff"]
    feature_cols = [c for c in feature_cols if c in df.columns]
    df["label"] = labels

    ml_df = df[feature_cols + ["label"]].dropna()
    if len(ml_df) < 200:
        logger.warning(f"Only {len(ml_df)} samples after dropna, using all available")

    # Create sequences
    seq_len = 30
    X_list, y_list = [], []
    values = ml_df[feature_cols].values.astype(np.float32)
    labels_arr = ml_df["label"].values.astype(int)
    # Map labels: -1→2 (SHORT), 0→0 (HOLD), 1→1 (LONG)
    labels_arr = np.where(labels_arr == -1, 2, labels_arr)

    for i in range(len(values) - seq_len):
        X_list.append(values[i:i + seq_len])
        y_list.append(labels_arr[i + seq_len])
    X = np.array(X_list)
    y = np.array(y_list)

    split = int(len(X) * 0.8)
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]
    logger.info(f"ML data: X={X.shape}, train={split}, test={len(X)-split}")

    model_results = {}
    for name in MODEL_REGISTRY:
        t1 = time.time()
        kwargs = {"epochs": 3, "batch_size": 32, "seed": 42}
        if name in ("lightgbm", "xgboost"):
            kwargs = {"n_estimators": 50, "seed": 42}
        model = get_model(name, **kwargs)
        model.fit(X_train, y_train)
        preds, confs = model.predict(X_test)
        acc = (preds == y_test).mean()
        elapsed = time.time() - t1
        model_results[name] = {"accuracy": acc, "mean_conf": confs.mean(), "time": elapsed}
        logger.info(f"  {name:22s} | acc={acc:.3f} | conf={confs.mean():.3f} | {elapsed:.1f}s")

    # =========================================================================
    # 7. ENSEMBLE — Stacking
    # =========================================================================
    sep("7. ENSEMBLE META-LEARNER")

    from src.ml.models.ensemble_meta_learner import EnsembleMetaLearner, EnsembleConfig

    ens_cfg = EnsembleConfig(
        model_names=["bilstm", "dilated_cnn", "lightgbm"],
        model_kwargs={
            "bilstm": {"epochs": 3, "batch_size": 32, "hidden_dim": 64},
            "dilated_cnn": {"epochs": 3, "batch_size": 32, "channels": 32},
            "lightgbm": {"n_estimators": 50},
        },
        meta_learner_type="logistic",
        seed=42,
    )
    ensemble = EnsembleMetaLearner(ens_cfg)
    ensemble.fit(X_train, y_train, X_test, y_test)
    ens_preds, ens_confs, ens_sizing = ensemble.predict(X_test)
    ens_acc = (ens_preds == y_test).mean()
    weights = ensemble.get_model_weights()

    logger.info(f"Ensemble accuracy: {ens_acc:.3f}")
    logger.info(f"Ensemble mean confidence: {ens_confs.mean():.3f}")
    logger.info(f"Sizing distribution: full={sum(ens_sizing==1.0)}, "
                f"half={sum(ens_sizing==0.5)}, skip={sum(ens_sizing==0.0)}")
    logger.info("Model weights:")
    for name, w in weights.items():
        logger.info(f"  {name}: {w:.3f}")

    # =========================================================================
    # 8. HYPEROPT — Quick 5-trial search
    # =========================================================================
    sep("8. HYPEROPT — 5 Trial Quick Search")

    from src.ml.training.hyperopt_engine import HyperoptEngine

    ho = HyperoptEngine(n_trials=5, loss_fn="sharpe", seed=42)
    ho.add_param("fast_sma", "int", low=5, high=20)
    ho.add_param("slow_sma", "int", low=20, high=60)
    ho.add_param("sl_pct", "float", low=0.01, high=0.05)
    ho.add_param("tp_pct", "float", low=0.02, high=0.08)

    def objective(trial, params):
        strat = SMACrossover(fast=params["fast_sma"], slow=params["slow_sma"])
        cfg = BacktestConfig(
            initial_capital=Decimal("10000"),
            sl_pct=params["sl_pct"], tp_pct=params["tp_pct"],
            max_bars=48, seed=42,
        )
        res = engine.run(df, strat, cfg)
        return HyperoptEngine.compute_loss(
            {"sharpe_ratio": res.metrics.sharpe_ratio}, "sharpe"
        )

    ho_result = ho.optimize(objective)
    logger.info(f"Best params: {ho_result.best_params}")
    logger.info(f"Best Sharpe (neg loss): {-ho_result.best_score:.3f}")

    # =========================================================================
    # 9. RL AGENT — Quick training
    # =========================================================================
    sep("9. RL ENSEMBLE — Quick Training")

    from src.ml.models.rl_agent import RLEnsemble

    rl = RLEnsemble(seed=42, hidden_dim=64, epsilon_decay_steps=500)
    rl.fit(X_train[:200], y_train[:200], n_episodes=1)
    rl_preds, rl_confs = rl.predict(X_test[:50])
    rl_acc = (rl_preds == y_test[:50]).mean()
    logger.info(f"RL Ensemble accuracy (50 samples): {rl_acc:.3f}")
    logger.info(f"RL mean confidence: {rl_confs.mean():.3f}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    sep("GOLIATH v2.0 — INTEGRATION TEST SUMMARY")

    elapsed_total = time.time() - t0
    print(f"""
  Data:         {len(ohlcv):,} bars (1H)
  Indicators:   {indicator_count} computed
  Labels:       {len(valid):,} (win rate {wins/max(wins+losses,1):.1%})
  Backtest:     {result.metrics.total_trades} trades, Sharpe={result.metrics.sharpe_ratio:.3f}
  Walk-Forward: {len(folds)} folds
  Model Zoo:    {len(MODEL_REGISTRY)} models trained
  Ensemble:     acc={ens_acc:.3f}, {len(weights)} models stacked
  Hyperopt:     {ho_result.n_trials} trials, best Sharpe={-ho_result.best_score:.3f}
  RL Ensemble:  3 DQN agents, acc={rl_acc:.3f}

  Total time:   {elapsed_total:.1f}s
  Status:       ALL SYSTEMS OPERATIONAL
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
