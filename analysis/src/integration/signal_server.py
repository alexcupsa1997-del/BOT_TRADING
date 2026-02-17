"""
Signal Server — HTTP API for the Go Gateway.

Exposes the TradingOrchestrator as a REST endpoint so the Gateway
can proxy AI signals to GoliathHybrid.mq5.

Runs on :8000 inside the Docker trading-net network.

Ref: FUSION_PLAN — Gateway ↔ Analysis bridge
"""

from __future__ import annotations

import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import pandas as pd
import re
from fastapi import FastAPI, HTTPException, Query
from loguru import logger

# Input validation
VALID_SYMBOL_RE = re.compile(r'^[A-Za-z0-9/]{2,20}$')
VALID_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}

from src.orchestrator import TradingOrchestrator, OrchestratorConfig
from src.integration.notifier import NotifierConfig


# =============================================================================
# DATA PROVIDER — Generates or fetches OHLCV data
# =============================================================================

class DataProvider:
    """Provides OHLCV data for the orchestrator.

    Tries ccxt live data first (if exchange keys configured),
    falls back to synthetic data for demo/testing.
    """

    def __init__(self):
        self._exchange = None
        self._cache: dict[str, tuple[float, pd.DataFrame]] = {}
        self._cache_ttl = 30.0  # seconds

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h",
                        limit: int = 500) -> pd.DataFrame:
        """Get OHLCV data, with caching to avoid hammering the exchange."""
        import time
        cache_key = f"{symbol}:{timeframe}"
        now = time.time()

        # Return cached if fresh
        if cache_key in self._cache:
            ts, df = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return df

        # Try live exchange
        df = await self._fetch_live(symbol, timeframe, limit)
        if df is not None and len(df) >= 30:
            self._cache[cache_key] = (now, df)
            return df

        # Fallback: synthetic data (for demo without exchange keys)
        logger.warning(f"Using synthetic data for {symbol}")
        df = self._generate_synthetic(symbol, limit)
        self._cache[cache_key] = (now, df)
        return df

    async def _fetch_live(self, symbol: str, timeframe: str,
                          limit: int) -> Optional[pd.DataFrame]:
        """Fetch from ccxt exchange if configured."""
        try:
            if self._exchange is None:
                api_key = os.getenv("GOLIATH_API_KEY")
                exchange_id = os.getenv("GOLIATH_EXCHANGE", "binance")
                if not api_key:
                    return None

                import ccxt.async_support as ccxt_async
                exchange_class = getattr(ccxt_async, exchange_id, None)
                if exchange_class is None:
                    return None
                self._exchange = exchange_class({
                    "apiKey": api_key,
                    "secret": os.getenv("GOLIATH_API_SECRET", ""),
                    "enableRateLimit": True,
                })

            raw = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not raw:
                return None

            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df
        except Exception as e:
            logger.debug(f"Live fetch failed: {e}")
            return None

    @staticmethod
    def _generate_synthetic(symbol: str, n: int = 500) -> pd.DataFrame:
        """Generate synthetic OHLCV for demo mode."""
        np.random.seed(hash(symbol) % 2**31)
        base = {"BTC": 50000, "ETH": 3000, "XAU": 1800}.get(
            symbol[:3], 1800
        )
        dates = pd.date_range("2025-01-01", periods=n, freq="1h")
        close = base + np.cumsum(np.random.normal(0, base * 0.002, n))
        high = close + np.abs(np.random.normal(base * 0.001, base * 0.0005, n))
        low = close - np.abs(np.random.normal(base * 0.001, base * 0.0005, n))
        open_ = close + np.random.normal(0, base * 0.0005, n)
        volume = np.random.lognormal(mean=10, sigma=0.5, size=n)
        return pd.DataFrame({
            "open": open_, "high": high, "low": low,
            "close": close, "volume": volume,
        }, index=dates)

    async def close(self):
        """Close exchange connection."""
        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None


# =============================================================================
# FASTAPI APP
# =============================================================================

data_provider = DataProvider()
orchestrator: Optional[TradingOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global orchestrator
    logger.info("Signal server starting...")
    notifier_config = NotifierConfig.from_env()
    orchestrator = TradingOrchestrator(OrchestratorConfig(
        enable_brain=False,
        notifier_config=notifier_config,
    ))
    logger.info("Orchestrator initialized (signal-only mode)")
    yield
    await data_provider.close()
    logger.info("Signal server shut down")


app = FastAPI(title="GOLIATH Signal Server", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "analysis"}


@app.get("/predict/{symbol}")
async def predict(
    symbol: str,
    timeframe: str = Query("H1", description="OHLCV timeframe"),
):
    """Run the orchestrator and return an AI signal."""
    if orchestrator is None:
        raise HTTPException(503, "Orchestrator not initialized")

    # Validate inputs
    if not VALID_SYMBOL_RE.match(symbol):
        raise HTTPException(400, "Invalid symbol format")
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(400, f"Invalid timeframe. Must be one of: {', '.join(sorted(VALID_TIMEFRAMES))}")

    # Map common MT5 symbol formats
    ccxt_symbol = _normalize_symbol(symbol)
    ohlcv = await data_provider.get_ohlcv(ccxt_symbol, _tf_to_ccxt(timeframe))

    if ohlcv is None or len(ohlcv) < 30:
        return {
            "direction": "HOLD",
            "confidence": 0.0,
            "reasoning": "Insufficient data",
            "source_tier": "CONSERVATIVE",
        }

    decision = orchestrator.analyze(symbol, timeframe, ohlcv)

    return {
        "direction": decision.action,
        "confidence": round(decision.confidence, 4),
        "stop_loss": round(decision.stop_loss, 2) if decision.stop_loss else 0.0,
        "take_profit": round(decision.take_profit, 2) if decision.take_profit else 0.0,
        "position_size_pct": round(decision.position_size_pct, 4),
        "reasoning": decision.reasoning,
        "source_tier": decision.source_tier.name,
    }


# =============================================================================
# HELPERS
# =============================================================================

def _normalize_symbol(symbol: str) -> str:
    """Convert MT5 symbol to ccxt format. XAUUSD -> XAU/USD, BTCUSD -> BTC/USD."""
    known = {
        "XAUUSD": "XAU/USD", "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD",
        "NZDUSD": "NZD/USD", "USDCHF": "USD/CHF", "BTCUSD": "BTC/USD",
        "BTCUSDT": "BTC/USDT", "ETHUSDT": "ETH/USDT",
    }
    upper = symbol.upper().replace("/", "")
    return known.get(upper, symbol)


def _tf_to_ccxt(timeframe: str) -> str:
    """Convert MT5/orchestrator timeframe to ccxt format. H1 -> 1h."""
    mapping = {
        "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
        "H1": "1h", "H4": "4h", "D1": "1d",
    }
    return mapping.get(timeframe, timeframe)


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Entry point to run the signal server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
