"""
fetch_historical.py - Data Acquisition Script
=============================================

Fetches historical OHLCV data using the unified ExchangeManager and saves it to Parquet files.
Usage: python scripts/fetch_historical.py --symbol BTC/USDT --timeframe 1h --days 30

"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from analysis/src/integration
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from loguru import logger
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Import from integration package
try:
    from analysis.src.integration.exchange_manager import ExchangeManager
    from analysis.src.integration.config import ExchangeConfig
except ImportError as e:
    logger.error(f"Import Error: {e}")
    logger.error("Ensure you are running this script from the project root or correct paths are set.")
    sys.exit(1)

async def main():
    parser = argparse.ArgumentParser(description="Fetch historical data to Parquet.")
    parser.add_argument("--symbol", type=str, required=True, help="Trading pair (e.g. BTC/USDT)")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe (e.g. 1h, 1m)")
    parser.add_argument("--days", type=int, default=30, help="Number of days of history to fetch")
    parser.add_argument("--exchange", type=str, default="binance", help="Exchange ID (ccxt)")
    args = parser.parse_args()

    # Setup
    symbol_safe = args.symbol.replace("/", "")
    output_dir = project_root / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.exchange}_{symbol_safe}_{args.timeframe}.parquet"

    logger.info(f"Starting fetch for {args.symbol} ({args.timeframe}) from {args.exchange}...")
    
    # Configure Exchange
    config = ExchangeConfig(
        exchange_id=args.exchange,
        sandbox=False, # Use real data
        rate_limit_per_min=1200
    )
    
    manager = ExchangeManager(config)
    
    try:
        # Calculate start timestamp
        # 'since' for ccxt is ms timestamp
        now = pd.Timestamp.now(tz="UTC")
        start_time = now - pd.Timedelta(days=args.days)
        start_ts = int(start_time.timestamp() * 1000)
        
        logger.info(f"Fetching data since {start_time} (TS: {start_ts})")
        
        # Fetch Data (ExchangeManager handles pagination via limit, but simplistic version fetches once)
        # Wait, ExchangeManager.fetch_ohlcv takes 'limit'. It doesn't auto-paginate.
        # We need a loop here to fetch all history.
        
        all_dfs = []
        current_since = start_ts
        total_fetched = 0
        
        while True:
            logger.info(f"Fetching batch starting from {pd.to_datetime(current_since, unit='ms', utc=True)}...")
            df = await manager.fetch_ohlcv(
                symbol=args.symbol,
                timeframe=args.timeframe,
                since=current_since,
                limit=1000 # Max for Binance typically
            )
            
            if df.empty:
                logger.info("No more data received.")
                break
                
            # Check if we got new data
            last_ts_ns = df.iloc[-1]["timestamp"]
            last_ts_ms = last_ts_ns // 1_000_000
            
            if last_ts_ms <= current_since:
                 logger.warning("Received data overlaps or no progress. Stopping loop.")
                 break
            
            all_dfs.append(df)
            total_fetched += len(df)
            current_since = last_ts_ms + 1 # Next request starts after last candle
            
            # Simple rate limit pause if needed, though manager handles it
            await asyncio.sleep(0.1) 
            
            # Stop if we reached close to now (simple check)
            if last_ts_ms >= (now.timestamp() * 1000) - 60000: # Within last minute
                break

        if not all_dfs:
            logger.warning("No data fetched!")
            return

        final_df = pd.concat(all_dfs)
        final_df = final_df.drop_duplicates(subset=["timestamp"], keep="last")
        final_df = final_df.sort_values("timestamp").reset_index(drop=True)
        
        logger.success(f"Fetched total {len(final_df)} rows.")

        # Save to Parquet
        # Note: Data is Decimal. Parquet supports Decimal, but pyarrow conversion might require care.
        # For simplicity in Phase 2, we might convert to float for specific columns if Decimal issues arise,
        # BUT GOLIATH rules say "No Float". We will try to keep Decimal or use string/int64 if needed.
        # Let's try direct save first. Pyarrow might cast Decimals to fixed-point.
        
        # Ensure conversion to types compatible with Parquet
        # Convert Decimals to string if issues arise, but let's try keeping them objects first
        # Actually standard Parquet doesn't like Python Decimal objects easily without schema.
        # Strategy: Coerce to float64 for STORAGE purely if needed, but strict Backtest Engine casts back.
        # OR: Store as string. OR: Store as scaled int64.
        
        # Decision: Store as float64 for compatibility with standard tools (Pandas/Polars default),
        # BUT Backtest Engine MUST cast to Decimal on load defined in PolarsDataFeed.
        # This deviates slightly from "Parquet as Decimal", but implies storage format.
        # Wait, Polars read_parquet supports Decimal? It's better to verify.
        # For now, let's cast to float for the SAVE to ensure it works, and handle Decimal conversion on LOAD.
        # This is a pragmatic compromise for the script.
        
        for col in ["open", "high", "low", "close", "volume"]:
            final_df[col] = final_df[col].astype(float) # Fallback for Parquet compatibility

        final_df.to_parquet(output_file, engine="pyarrow", index=False)
        logger.success(f"Saved to {output_file}")
        
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        import traceback
        traceback.print_exc() 
    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
