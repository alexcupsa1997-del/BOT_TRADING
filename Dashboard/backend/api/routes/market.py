"""
Market data endpoints.
GET /api/market/data/{symbol}    - OHLCV data for charting
GET /api/market/signals/{symbol} - ML signal from gateway/analysis
GET /api/market/files            - Available data files
"""

import os
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException

from config import settings
from services import gateway_service

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/data/{symbol}")
async def get_market_data(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe"),
    limit: int = Query(200, ge=1, le=5000),
):
    """Load OHLCV data from parquet/csv files in data/ directory."""
    data_dir = Path(settings.data_dir)
    if not data_dir.exists():
        raise HTTPException(status_code=404, detail="Data directory not found")

    # Search for matching data files
    candidates = []
    for ext in ("*.parquet", "*.csv"):
        for f in data_dir.rglob(ext):
            if symbol.lower().replace("/", "") in f.name.lower().replace("/", ""):
                if timeframe.lower() in f.name.lower():
                    candidates.append(f)

    if not candidates:
        # Try broader match (just symbol)
        for ext in ("*.parquet", "*.csv"):
            for f in data_dir.rglob(ext):
                if symbol.lower().replace("/", "") in f.name.lower().replace("/", ""):
                    candidates.append(f)

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No data file found for {symbol} {timeframe}",
        )

    # Use most recent file
    file_path = max(candidates, key=os.path.getmtime)

    try:
        if file_path.suffix == ".parquet":
            import polars as pl
            df = pl.read_parquet(str(file_path))
        else:
            import polars as pl
            df = pl.read_csv(str(file_path))

        # Normalize column names
        col_map = {}
        for col in df.columns:
            lower = col.lower()
            if "time" in lower or "date" in lower:
                col_map[col] = "timestamp"
            elif lower == "open":
                col_map[col] = "open"
            elif lower == "high":
                col_map[col] = "high"
            elif lower == "low":
                col_map[col] = "low"
            elif lower == "close":
                col_map[col] = "close"
            elif "vol" in lower:
                col_map[col] = "volume"
        df = df.rename(col_map)

        # Take last N rows
        df = df.tail(limit)

        # Convert to list of dicts with string values for decimals
        records = []
        for row in df.iter_rows(named=True):
            records.append({
                "timestamp": str(row.get("timestamp", "")),
                "open": str(row.get("open", "0")),
                "high": str(row.get("high", "0")),
                "low": str(row.get("low", "0")),
                "close": str(row.get("close", "0")),
                "volume": str(row.get("volume", "0")),
            })

        return {"data": records, "meta": {"file": file_path.name, "count": len(records)}}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading data: {e}")


@router.get("/signals/{symbol}")
async def get_signal(
    symbol: str,
    timeframe: str = Query("H1", description="Timeframe for signal"),
):
    """Fetch ML signal from gateway (proxy to analysis server)."""
    signal = await gateway_service.get_signal(symbol, timeframe)
    if signal is None:
        return {"data": None, "error": "Signal service unavailable"}
    return {"data": signal}


@router.get("/files")
async def list_data_files():
    """List available data files for charting."""
    data_dir = Path(settings.data_dir)
    if not data_dir.exists():
        return {"data": []}

    files = []
    for ext in ("*.parquet", "*.csv"):
        for f in data_dir.rglob(ext):
            files.append({
                "name": f.name,
                "path": str(f.relative_to(data_dir)),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            })

    return {"data": sorted(files, key=lambda x: x["name"])}
