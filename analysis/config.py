"""
GOLIATH Configuration

Centralized configuration for the trading system.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path


# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PARQUET_DIR = DATA_DIR  # Parquet files from Gateway
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"


# =============================================================================
# ASSET UNIVERSE
# =============================================================================

SYMBOLS: Dict[str, List[str]] = {
    "forex_majors": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
    "forex_crosses": ["EURGBP", "EURJPY", "GBPJPY"],
    "indices": ["US30", "NAS100", "SPX500", "GER40"],
    "commodities": ["XAUUSD", "XAGUSD", "USOIL"],
    "crypto": ["BTCUSD", "ETHUSD"],
}

# Flattened list of all symbols
ALL_SYMBOLS: List[str] = [s for group in SYMBOLS.values() for s in group]

# Symbol ID mapping (matches MQL5 Bridge)
SYMBOL_ID_MAP: Dict[str, int] = {symbol: i + 1 for i, symbol in enumerate(ALL_SYMBOLS)}


# =============================================================================
# TIMEFRAMES
# =============================================================================

TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4", "D1"]

# Pandas resample rules
TIMEFRAME_MAP = {
    "M1": "1T",
    "M5": "5T",
    "M15": "15T",
    "H1": "1H",
    "H4": "4H",
    "D1": "1D",
}


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

# Fractional Differencing
FRACDIFF_D = 0.4  # Differencing order
FRACDIFF_THRESHOLD = 1e-5

# Triple Barrier
TP_PERCENT = 0.02  # 2% take profit
SL_PERCENT = 0.01  # 1% stop loss
MAX_HOLDING_BARS = 60  # 1 hour for M1 data

# EMAs to compute
EMA_PERIODS = [9, 21, 50, 200]


# =============================================================================
# ML TRAINING
# =============================================================================

# Sequence length for LSTM/Transformer
SEQUENCE_LENGTH = 60

# Train/Val/Test split
TRAIN_RATIO = 0.7
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Batch size
BATCH_SIZE = 64

# Device
DEVICE = "cuda"  # or "cpu"


# =============================================================================
# EXCHANGE GATEWAY (Fase 1 — FUSION_PLAN)
# =============================================================================

# Default exchange for data and trading
DEFAULT_EXCHANGE = "binance"

# Safety modes (rules-security.md §3)
EXCHANGE_SANDBOX = True   # Use testnet by default
EXCHANGE_DRY_RUN = True   # Simulate orders locally (no real trades)

# Supported exchanges (actively tested)
SUPPORTED_EXCHANGES = ["binance", "bybit", "kraken", "okx", "bitget", "kucoin"]

# CCXT timeframe mapping (GOLIATH → CCXT format)
CCXT_TIMEFRAME_MAP = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "4h", "D1": "1d", "W1": "1w",
}

# WebSocket stream settings
WS_BUFFER_SIZE = 1000          # Ring buffer depth per symbol (latest-wins)
WS_HEARTBEAT_INTERVAL = 30.0   # Seconds between heartbeat checks
WS_MAX_RECONNECT = 5           # Max reconnect attempts before fail-safe

# Rate limiting
RATE_LIMIT_RETRIES = 3  # Max retries on rate limit before giving up

# API credentials loaded from env vars (rules-security.md §1):
#   EXCHANGE_API_KEY, EXCHANGE_API_SECRET, EXCHANGE_PASSWORD


# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"


# =============================================================================
# EXCHANGE CONNECTIVITY (FASE 1)
# =============================================================================

@dataclass
class ExchangeConfig:
    """Configuration for exchange connectivity via ccxt.

    API credentials are loaded exclusively from environment variables.
    Never store secrets in code or config files.
    """
    exchange_id: str = "binance"
    sandbox: bool = True
    api_key: str = field(default_factory=lambda: os.environ.get("EXCHANGE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.environ.get("EXCHANGE_API_SECRET", ""))
    password: str = field(default_factory=lambda: os.environ.get("EXCHANGE_PASSWORD", ""))
    rate_limit_per_min: int = 1200
    timeout_ms: int = 30000
    retry_count: int = 3
    retry_delay_base: float = 1.0
    default_timeframe: str = "1h"

    def to_ccxt_dict(self) -> dict:
        """Convert to ccxt constructor kwargs."""
        cfg = {
            "sandbox": self.sandbox,
            "timeout": self.timeout_ms,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
        if self.api_key:
            cfg["apiKey"] = self.api_key
        if self.api_secret:
            cfg["secret"] = self.api_secret
        if self.password:
            cfg["password"] = self.password
        return cfg
