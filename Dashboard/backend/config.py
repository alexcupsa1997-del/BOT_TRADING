"""
Dashboard Backend Configuration
================================
All settings loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


# Resolve project root (BOT_TRADING/)
_BACKEND_DIR = Path(__file__).resolve().parent
_DASHBOARD_DIR = _BACKEND_DIR.parent
_PROJECT_ROOT = _DASHBOARD_DIR.parent


class Settings(BaseSettings):
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Redis key names (match mock_dashboard_data.py)
    redis_key_status: str = "goliath:status"
    redis_key_orders: str = "goliath:orders"
    redis_key_logs: str = "goliath:logs:critical"
    redis_key_positions: str = "goliath:positions"
    redis_key_equity_curve: str = "goliath:equity_curve"
    redis_key_trade_history: str = "goliath:trade_history"

    # External services
    gateway_url: str = "http://localhost:8080"
    analysis_url: str = "http://localhost:8000"

    # Paths (resolved relative to project root)
    engine_root: str = str(_PROJECT_ROOT / "engine")
    data_dir: str = str(_PROJECT_ROOT / "data")
    config_path: str = str(_PROJECT_ROOT / "config" / "paper_trading.json")
    log_dir: str = str(_PROJECT_ROOT / "logs")
    results_dir: str = str(_BACKEND_DIR / "results")

    # Project root for sys.path
    project_root: str = str(_PROJECT_ROOT)

    # Dashboard server
    host: str = "0.0.0.0"
    port: int = 8888
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_prefix = "DASHBOARD_"
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
