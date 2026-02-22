export interface ApiResponse<T> {
  data: T;
  error?: string;
  meta?: Record<string, unknown>;
}

export interface SystemStatus {
  cpu_percent: number;
  ram_percent: number;
  ram_mb: number;
  ram_total_mb?: number;
  disk_usage: number;
  disk_used_gb?: number;
  disk_total_gb?: number;
  uptime_seconds: number;
  pg_connections: number;
  pg_max_connections: number;
  redis_latency_history: [number, number][];
  redis_latency_ms?: number;
  daily_pnl: number;
  pnl_percent: number;
  active_strategy: string;
  open_positions: number;
  trades_count: number;
}

export interface ServiceHealth {
  name: string;
  status: 'ok' | 'error' | 'unreachable';
  latency_ms?: number;
  details?: string;
}

export interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: string;
  status: string;
}

export interface Position {
  symbol: string;
  quantity: string;
  avg_price: string;
  current_price: string;
  unrealized_pnl: string;
  side: 'LONG' | 'SHORT';
}

export interface Trade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: string;
  quantity: string;
  pnl: string;
  time: string;
  timestamp?: string;
}

export interface TradingData {
  daily_pnl: number;
  pnl_percent: number;
  active_strategy: string;
  open_positions: number;
  trades_count: number;
  orders: Order[];
  positions: Position[];
  equity_curve: EquityPoint[];
  trade_history?: Trade[];
}

export interface EquityPoint {
  timestamp: string;
  total_equity: string;
  cash: string;
}

export interface BacktestRequest {
  data_file: string;
  symbol: string;
  initial_cash: string;
  strategy?: string;
  strategy_params?: Record<string, unknown>;
  start_date?: string;
  end_date?: string;
}

export interface BacktestRun {
  run_id: string;
  status: string;
  symbol: string;
  strategy: string;
  created_at: string;
}

export interface BacktestResult {
  run_id: string;
  status: string;
  params: Record<string, unknown>;
  metrics?: {
    initial_capital: string;
    final_equity: string;
    total_return_pct: string;
    sharpe_ratio: string;
    sortino_ratio: string;
    max_drawdown_pct: string;
  };
  equity_curve: Record<string, string>[];
  error?: string;
}

export interface TradingConfig {
  mode: string;
  symbols: string[];
  timeframe: string;
  balance: number;
  strategy: {
    name: string;
    model_path: string;
    confidence_threshold: number;
  };
  execution: {
    gateway_url: string;
    risk_limit_per_trade: number;
    max_open_trades: number;
  };
  logging: {
    level: string;
    file: string;
  };
}

export interface OHLCVBar {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

export interface DataFile {
  name: string;
  path: string;
  size_mb: number;
}

export interface ModelInfo {
  model_type: string;
  architecture: Record<string, unknown>;
  device: string;
  available_models: { name: string; path: string; size_mb: number }[];
  note: string;
}

export interface LogFile {
  name: string;
  size_kb: number;
  modified: number;
}
