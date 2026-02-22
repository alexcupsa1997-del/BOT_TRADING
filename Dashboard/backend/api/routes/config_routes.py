"""
Configuration CRUD endpoints.
GET/PUT /api/config - Full config
GET/PUT /api/config/symbols - Symbols list
GET/PUT /api/config/strategy - Strategy parameters
GET/PUT /api/config/risk - Risk limits
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services import config_service
from services.redis_service import redis_service

router = APIRouter(prefix="/api/config", tags=["config"])


class SymbolsUpdate(BaseModel):
    symbols: list[str]


class StrategyUpdate(BaseModel):
    name: str
    model_path: str
    confidence_threshold: float


class RiskUpdate(BaseModel):
    risk_limit_per_trade: float
    max_open_trades: int


class FullConfigUpdate(BaseModel):
    mode: Optional[str] = None
    symbols: Optional[list[str]] = None
    timeframe: Optional[str] = None
    balance: Optional[float] = None
    strategy: Optional[dict] = None
    execution: Optional[dict] = None
    logging: Optional[dict] = None


@router.get("")
async def get_config():
    """Read full trading configuration."""
    config = config_service.read_config()
    if not config:
        raise HTTPException(status_code=404, detail="Config file not found")
    return {"data": config}


@router.put("")
async def update_config(body: FullConfigUpdate):
    """Update full configuration."""
    current = config_service.read_config()
    updates = body.model_dump(exclude_none=True)
    current.update(updates)
    config_service.write_config(current)
    await redis_service.publish_config_update()
    return {"data": current}


@router.get("/symbols")
async def get_symbols():
    """Read symbols list."""
    config = config_service.read_config()
    return {"data": config.get("symbols", [])}


@router.put("/symbols")
async def update_symbols(body: SymbolsUpdate):
    """Update symbols list."""
    config = config_service.update_config_section("symbols", body.symbols)
    await redis_service.publish_config_update()
    return {"data": config.get("symbols", [])}


@router.get("/strategy")
async def get_strategy():
    """Read strategy configuration."""
    config = config_service.read_config()
    return {"data": config.get("strategy", {})}


@router.put("/strategy")
async def update_strategy(body: StrategyUpdate):
    """Update strategy parameters."""
    config = config_service.update_config_section("strategy", body.model_dump())
    await redis_service.publish_config_update()
    return {"data": config.get("strategy", {})}


@router.get("/risk")
async def get_risk():
    """Read risk/execution limits."""
    config = config_service.read_config()
    return {"data": config.get("execution", {})}


@router.put("/risk")
async def update_risk(body: RiskUpdate):
    """Update risk limits."""
    config = config_service.read_config()
    execution = config.get("execution", {})
    execution.update(body.model_dump())
    updated = config_service.update_config_section("execution", execution)
    await redis_service.publish_config_update()
    return {"data": updated.get("execution", {})}
