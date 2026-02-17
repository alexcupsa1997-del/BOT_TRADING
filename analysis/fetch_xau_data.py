#!/usr/bin/env python3
"""
Fetch XAU/USD Data from Yahoo Finance
=====================================
Downloads daily data for Gold (GC=F or XAU-USD) since 2000.
Saves to data/xau_usd_daily.parquet in a format compatible with Goliath.
"""

import os
import sys
import yfinance as yf
import pandas as pd
from loguru import logger

# Configuration
SYMBOL = "GC=F"  # Gold Futures (closest to XAU/USD spot for volume data)
# SYMBOL = "XAU-USD" # Spot gold (often lacks volume on Yahoo)
START_DATE = "2000-01-01"
OUTPUT_DIR = "data"
OUTPUT_FILE = f"{OUTPUT_DIR}/xau_usd_daily.parquet"

def fetch_data():
    logger.info(f"Fetching data for {SYMBOL} from {START_DATE}...")
    
    try:
        # Fetch data
        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(start=START_DATE, interval="1d")
        
        if df.empty:
            logger.error("No data fetched! Check symbol or connectivity.")
            return
            
        logger.info(f"Fetched {len(df)} rows.")
        
        # Reset index to get Date as column
        df = df.reset_index()
        
        # Renaissance/Goliath Standard Columns
        # Date -> timestamp (ns)
        # Open, High, Low, Close, Volume
        
        # Rename columns standard
        df = df.rename(columns={
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        
        # Keep only relevant columns
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        df = df[cols]
        
        # Ensure timestamp is datetime64[ns] (remove timezone)
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
        
        # Ensure numeric columns are float32/64
        for c in ['open', 'high', 'low', 'close', 'volume']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
        # Drop NaN
        df = df.dropna()
        
        # Save to parquet
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        df.to_parquet(OUTPUT_FILE, compression='snappy')
        
        logger.success(f"Data saved to {OUTPUT_FILE}")
        logger.info(f"Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"Rows: {len(df)}")
        
        # Preview
        print(df.tail())
        
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fetch_data()
