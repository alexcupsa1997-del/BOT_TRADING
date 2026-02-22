"""
Trading data endpoints.
GET /api/trading/status       - Active strategy, PnL, positions count
GET /api/trading/orders       - Active orders
GET /api/trading/positions    - Open positions detail
GET /api/trading/equity-curve - Equity curve data
GET /api/trading/history      - Closed trade history
"""

from fastapi import APIRouter

from services.redis_service import redis_service

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.get("/status")
async def get_trading_status():
    """Trading summary from Redis."""
    status = await redis_service.get_system_status()
    orders = await redis_service.get_orders()

    if status is None:
        return {"data": {
            "daily_pnl": "0",
            "pnl_percent": "0",
            "active_strategy": "N/A",
            "open_positions": 0,
            "trades_count": 0,
            "orders": [],
        }}

    return {"data": {
        "daily_pnl": str(status.get("daily_pnl", 0)),
        "pnl_percent": str(status.get("pnl_percent", 0)),
        "active_strategy": status.get("active_strategy", "N/A"),
        "open_positions": status.get("open_positions", 0),
        "trades_count": status.get("trades_count", 0),
        "orders": orders,
    }}


@router.get("/orders")
async def get_active_orders():
    """List of active orders."""
    orders = await redis_service.get_orders()
    return {"data": orders}


@router.get("/positions")
async def get_positions():
    """Open positions detail."""
    positions = await redis_service.get_positions()
    return {"data": positions}


@router.get("/equity-curve")
async def get_equity_curve():
    """Equity curve data points."""
    curve = await redis_service.get_equity_curve()
    return {"data": curve}


@router.get("/history")
async def get_trade_history():
    """Closed trades history."""
    history = await redis_service.get_trade_history()
    return {"data": history}
