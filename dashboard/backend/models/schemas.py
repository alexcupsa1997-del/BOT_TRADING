"""
Pydantic models for API request/response types.
All financial values serialized as strings (Decimal precision).
"""

from pydantic import BaseModel
from typing import Optional


# ── System ─────────────────────────────────────────────────────────

class ServiceHealth(BaseModel):
    name: str
    status: str  # "ok", "error", "unreachable"
    latency_ms: Optional[float] = None
    details: Optional[str] = None


class SystemStatus(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_mb: int
    disk_usage: float
    uptime_seconds: int
    pg_connections: int
    pg_max_connections: int
    redis_latency_history: list
    daily_pnl: str
    pnl_percent: str
    active_strategy: str
    open_positions: int
    trades_count: int
    services: Optional[list[ServiceHealth]] = None


# ── Trading ────────────────────────────────────────────────────────

class Order(BaseModel):
    id: str
    symbol: str
    side: str  # BUY / SELL
    price: str  # Decimal as string
    status: str  # OPEN / FILLED / CANCELLED


class Position(BaseModel):
    symbol: str
    quantity: str  # Decimal as string
    avg_price: str
    current_price: str
    unrealized_pnl: str
    side: str  # LONG / SHORT


class EquityPoint(BaseModel):
    timestamp: str
    total_equity: str
    cash: str


class TradeRecord(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: str
    price: str
    timestamp: str
    pnl: Optional[str] = None


class TradingStatus(BaseModel):
    daily_pnl: str
    pnl_percent: str
    active_strategy: str
    open_positions: int
    trades_count: int
    orders: list[Order]


# ── Backtest ───────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    data_file: str
    symbol: str
    initial_cash: str  # Decimal as string
    strategy: str = "breakout"
    strategy_params: dict = {}
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class BacktestMetrics(BaseModel):
    initial_capital: str
    final_equity: str
    total_return_pct: str
    sharpe_ratio: str
    sortino_ratio: str
    max_drawdown_pct: str


class BacktestResult(BaseModel):
    run_id: str
    status: str  # running / completed / failed
    params: dict
    metrics: Optional[BacktestMetrics] = None
    equity_curve: list[dict] = []
    error: Optional[str] = None


class BacktestListItem(BaseModel):
    run_id: str
    status: str
    symbol: str
    strategy: str
    created_at: str


# ── Configuration ──────────────────────────────────────────────────

class StrategyConfig(BaseModel):
    name: str
    model_path: str
    confidence_threshold: float


class ExecutionConfig(BaseModel):
    gateway_url: str
    risk_limit_per_trade: float
    max_open_trades: int


class LoggingConfig(BaseModel):
    level: str
    file: str


class TradingConfig(BaseModel):
    mode: str
    symbols: list[str]
    timeframe: str
    balance: str  # Decimal as string
    strategy: StrategyConfig
    execution: ExecutionConfig
    logging: LoggingConfig


# ── Logs ───────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    message: str
    level: Optional[str] = None
    timestamp: Optional[str] = None
    source: Optional[str] = None


# ── Market ─────────────────────────────────────────────────────────

class OHLCVBar(BaseModel):
    timestamp: str
    open: str
    high: str
    low: str
    close: str
    volume: str


class MLSignal(BaseModel):
    symbol: str
    action: str  # BUY / SELL / HOLD
    confidence: str
    tp_multiplier: Optional[str] = None
    sl_multiplier: Optional[str] = None
    timestamp: str


# ── ML ─────────────────────────────────────────────────────────────

class ModelInfo(BaseModel):
    model_type: str
    architecture: dict
    device: str
    input_dim: Optional[int] = None
    scaler_loaded: bool = False


# ── Generic response wrapper ──────────────────────────────────────

class APIResponse(BaseModel):
    data: Optional[dict | list] = None
    error: Optional[str] = None
    meta: Optional[dict] = None
