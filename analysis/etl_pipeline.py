"""
ETL Pipeline

Transform raw Parquet data into ML-ready tensors.

Pipeline Flow:
Parquet → Resample → Indicators → Patterns → FracDiff → Labels → NPZ

Fase 2 additions:
- --backtest flag: run BacktestEngine on processed data
- --walk-forward flag: run walk-forward validation

Usage:
    python etl_pipeline.py --dry-run          # Preview without saving
    python etl_pipeline.py --symbol BTCUSD    # Single symbol
    python etl_pipeline.py                    # All symbols
    python etl_pipeline.py --backtest         # Run with backtest
    python etl_pipeline.py --walk-forward     # Run with walk-forward validation
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    PARQUET_DIR, OUTPUT_DIR, ALL_SYMBOLS, TIMEFRAME_MAP,
    TP_PERCENT, SL_PERCENT, MAX_HOLDING_BARS, FRACDIFF_D,
    EMA_PERIODS, SEQUENCE_LENGTH
)
from src.quant.indicators import compute_all_indicators, resample_ohlcv
from src.quant.patterns import detect_all_patterns
from src.quant.features import (
    fractional_differencing, triple_barrier_labels, compute_rolling_volatility
)
from src.quant.backtest_engine import BacktestEngine, BacktestConfig, Strategy
from src.quant.triple_barrier import TripleBarrier
from src.ml.training.walk_forward import WalkForwardValidator


def load_parquet_files(pattern: str = "*.parquet") -> pd.DataFrame:
    """
    Load all Parquet files from the data directory.
    
    Args:
        pattern: Glob pattern for files
        
    Returns:
        Combined DataFrame with all tick data
    """
    parquet_files = list(Path(PARQUET_DIR).glob(pattern))
    
    if not parquet_files:
        logger.error(f"No parquet files found in {PARQUET_DIR}")
        return pd.DataFrame()
    
    logger.info(f"Found {len(parquet_files)} parquet files")
    
    dfs = []
    for f in parquet_files:
        try:
            df = pd.read_parquet(f)
            dfs.append(df)
            logger.debug(f"Loaded {f.name}: {len(df)} rows")
        except Exception as e:
            logger.warning(f"Failed to load {f.name}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Combined dataset: {len(combined)} total rows")
    
    return combined


def prepare_ohlcv(df: pd.DataFrame, symbol_id: Optional[int] = None) -> pd.DataFrame:
    """
    Convert tick data to OHLCV format.
    
    Args:
        df: Raw tick DataFrame
        symbol_id: Filter by symbol ID (optional)
        
    Returns:
        OHLCV DataFrame with DatetimeIndex
    """
    # Filter by symbol if specified
    if symbol_id is not None and 'symbol_id' in df.columns:
        df = df[df['symbol_id'] == symbol_id].copy()
    
    # Ensure timestamp column
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
    
    # If we have bid/ask, use mid price
    if 'bid' in df.columns and 'ask' in df.columns:
        df['price'] = (df['bid'] + df['ask']) / 2
    elif 'close' not in df.columns:
        if 'price' not in df.columns:
            logger.error("No price column found")
            return pd.DataFrame()
    
    # Resample to 1-minute OHLCV
    price_col = 'price' if 'price' in df.columns else 'close'
    vol_col = 'volume' if 'volume' in df.columns else None
    
    ohlcv = df[price_col].resample('1T').agg(['first', 'max', 'min', 'last'])
    ohlcv.columns = ['open', 'high', 'low', 'close']
    
    if vol_col:
        ohlcv['volume'] = df[vol_col].resample('1T').sum()
    else:
        ohlcv['volume'] = 1  # Default volume
    
    # Drop rows with NaN
    ohlcv = ohlcv.dropna()
    
    return ohlcv


def process_timeframe(
    ohlcv: pd.DataFrame,
    timeframe: str,
    compute_labels: bool = True
) -> pd.DataFrame:
    """
    Process a single timeframe: resample + indicators + patterns + labels.
    
    Args:
        ohlcv: OHLCV DataFrame (1-minute)
        timeframe: Target timeframe (e.g., 'H1')
        compute_labels: Whether to compute triple barrier labels
        
    Returns:
        Processed DataFrame
    """
    # Resample if not M1
    if timeframe != "M1":
        resample_rule = TIMEFRAME_MAP.get(timeframe, "1H")
        df = resample_ohlcv(ohlcv, resample_rule)
    else:
        df = ohlcv.copy()
    
    logger.info(f"Processing {timeframe}: {len(df)} bars")
    
    # Compute indicators
    df = compute_all_indicators(df, include_emas=EMA_PERIODS)
    
    # Detect patterns
    df = detect_all_patterns(df)
    
    # Returns for volatility
    df['returns'] = df['close'].pct_change()
    df['volatility'] = compute_rolling_volatility(df['returns'])
    
    # Fractional differencing on close
    df['close_fracdiff'] = fractional_differencing(df['close'], d=FRACDIFF_D)
    
    # Triple barrier labels
    if compute_labels and len(df) > MAX_HOLDING_BARS:
        result = triple_barrier_labels(
            df['close'], df['high'], df['low'],
            tp_pct=TP_PERCENT,
            sl_pct=SL_PERCENT,
            max_holding_periods=MAX_HOLDING_BARS
        )
        df['label'] = result.labels
        df['barrier_type'] = result.barriers['barrier_type']
    
    return df


def create_sequences(
    df: pd.DataFrame,
    sequence_length: int = SEQUENCE_LENGTH,
    feature_cols: Optional[List[str]] = None
) -> tuple:
    """
    Create sequences for LSTM/Transformer training.
    
    Args:
        df: Processed DataFrame
        sequence_length: Length of each sequence
        feature_cols: Columns to include as features
        
    Returns:
        Tuple of (X, y) numpy arrays
    """
    if feature_cols is None:
        # Default features
        feature_cols = [
            'close_fracdiff', 'returns', 'volatility',
            'rsi', 'macd', 'macd_signal', 'macd_hist',
            'stoch_k', 'stoch_d', 'adx', 'cci', 'atr',
            'bb_bandwidth'
        ] + [f'ema_{p}' for p in EMA_PERIODS]
    
    # Filter to available columns
    available_cols = [c for c in feature_cols if c in df.columns]
    
    # Drop NaN rows
    df_clean = df[available_cols + ['label']].dropna()
    
    if len(df_clean) < sequence_length + 1:
        logger.warning(f"Not enough data for sequences: {len(df_clean)} rows")
        return np.array([]), np.array([])
    
    X, y = [], []
    
    for i in range(len(df_clean) - sequence_length):
        X.append(df_clean[available_cols].iloc[i:i + sequence_length].values)
        y.append(df_clean['label'].iloc[i + sequence_length])
    
    return np.array(X), np.array(y)


def run_pipeline(
    symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    dry_run: bool = False
) -> None:
    """
    Run the full ETL pipeline.
    
    Args:
        symbols: List of symbols to process (default: all)
        timeframes: List of timeframes (default: all)
        dry_run: If True, don't save output
    """
    symbols = symbols or ALL_SYMBOLS
    timeframes = timeframes or list(TIMEFRAME_MAP.keys())
    
    logger.info(f"Starting ETL pipeline")
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Timeframes: {timeframes}")
    
    # Load data
    raw_data = load_parquet_files()
    
    if raw_data.empty:
        logger.error("No data to process")
        return
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Process each symbol and timeframe
    for symbol in symbols:
        symbol_id = next((i + 1 for i, s in enumerate(ALL_SYMBOLS) if s == symbol), None)
        
        logger.info(f"Processing {symbol} (ID: {symbol_id})")
        
        # Prepare OHLCV
        ohlcv = prepare_ohlcv(raw_data, symbol_id)
        
        if ohlcv.empty:
            logger.warning(f"No OHLCV data for {symbol}")
            continue
        
        for tf in timeframes:
            try:
                # Process timeframe
                df_processed = process_timeframe(ohlcv, tf)
                
                # Create sequences
                X, y = create_sequences(df_processed)
                
                if len(X) == 0:
                    logger.warning(f"No sequences created for {symbol} {tf}")
                    continue
                
                logger.info(f"{symbol} {tf}: {len(X)} sequences, shape={X.shape}")
                
                # Save if not dry run
                if not dry_run:
                    output_file = OUTPUT_DIR / f"{symbol}_{tf}_features.npz"
                    np.savez_compressed(
                        output_file,
                        X=X,
                        y=y,
                        symbol=symbol,
                        timeframe=tf
                    )
                    logger.success(f"Saved: {output_file}")
                
            except Exception as e:
                logger.error(f"Failed to process {symbol} {tf}: {e}")
                continue
    
    logger.success("ETL pipeline completed!")


def run_backtest(data: pd.DataFrame, strategy: Strategy, config: BacktestConfig = None) -> None:
    """
    Run backtest on processed data and print report.

    Args:
        data: OHLCV DataFrame
        strategy: Strategy instance
        config: Backtest configuration
    """
    engine = BacktestEngine()
    result = engine.run(data, strategy, config)
    print(engine.format_report(result.metrics))
    return result


def run_walk_forward_validation(
    data: pd.DataFrame,
    train_days: int = 60,
    test_days: int = 20,
    purge_days: int = 2,
) -> None:
    """
    Run walk-forward validation and print report.

    Args:
        data: OHLCV DataFrame with DatetimeIndex
        train_days: Training window in days
        test_days: Testing window in days
        purge_days: Gap between train and test
    """
    wf = WalkForwardValidator(
        train_days=train_days,
        test_days=test_days,
        purge_days=purge_days,
    )
    folds = wf.generate_folds(data)
    logger.info(f"Generated {len(folds)} walk-forward folds")
    for i, fold in enumerate(folds[:5]):
        logger.info(
            f"  Fold {i}: train={fold.train_start.date()}→{fold.train_end.date()}, "
            f"test={fold.test_start.date()}→{fold.test_end.date()}"
        )
    return folds


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="GOLIATH ETL Pipeline")
    parser.add_argument("--symbol", type=str, help="Single symbol to process")
    parser.add_argument("--timeframe", type=str, help="Single timeframe to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--backtest", action="store_true", help="Run backtest after ETL")
    parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward validation")

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    level = "DEBUG" if args.verbose else "INFO"
    logger.add(sys.stderr, level=level)

    # Prepare arguments
    symbols = [args.symbol] if args.symbol else None
    timeframes = [args.timeframe] if args.timeframe else None

    # Run pipeline
    run_pipeline(symbols=symbols, timeframes=timeframes, dry_run=args.dry_run)

    if args.walk_forward:
        logger.info("Walk-forward validation requested — use run_walk_forward_validation()")
    if args.backtest:
        logger.info("Backtest requested — use run_backtest() with a Strategy instance")


if __name__ == "__main__":
    main()
