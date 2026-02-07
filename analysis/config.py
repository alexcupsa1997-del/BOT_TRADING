"""
GOLIATH Configuration

Centralized configuration for the trading system.
"""

from typing import List, Dict
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
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
