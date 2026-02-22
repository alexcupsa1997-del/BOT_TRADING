"""
WebSocket stream endpoints.
Real-time data pushed to frontend via WebSocket.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ws.manager import ws_manager
from services.redis_service import redis_service
from services import system_service

router = APIRouter()


@router.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    """Stream system status every second."""
    await ws_manager.connect(websocket, "status")
    try:
        while True:
            # Try Redis first (mock or real engine data)
            status = await redis_service.get_system_status()
            if status is None:
                # Fallback to psutil-only metrics
                status = system_service.get_system_metrics()
                status.update({
                    "pg_connections": 0,
                    "pg_max_connections": 100,
                    "redis_latency_history": [],
                    "daily_pnl": 0,
                    "pnl_percent": 0,
                    "active_strategy": "N/A",
                    "open_positions": 0,
                    "trades_count": 0,
                })

            # Add Redis latency
            redis_latency = await redis_service.get_latency_ms()
            status["redis_latency_ms"] = round(redis_latency, 2)

            await websocket.send_json(status)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "status")
    except Exception:
        ws_manager.disconnect(websocket, "status")


@router.websocket("/ws/trading")
async def ws_trading(websocket: WebSocket):
    """Stream trading data (orders, positions, PnL) every second."""
    await ws_manager.connect(websocket, "trading")
    try:
        while True:
            status = await redis_service.get_system_status()
            orders = await redis_service.get_orders()
            positions = await redis_service.get_positions()
            equity_curve = await redis_service.get_equity_curve()

            data = {
                "daily_pnl": status.get("daily_pnl", 0) if status else 0,
                "pnl_percent": status.get("pnl_percent", 0) if status else 0,
                "active_strategy": status.get("active_strategy", "N/A") if status else "N/A",
                "open_positions": status.get("open_positions", 0) if status else 0,
                "trades_count": status.get("trades_count", 0) if status else 0,
                "orders": orders,
                "positions": positions,
                "equity_curve": equity_curve[-100:] if equity_curve else [],
            }

            await websocket.send_json(data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "trading")
    except Exception:
        ws_manager.disconnect(websocket, "trading")


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    """Stream critical logs. Pushes new entries as they appear."""
    await ws_manager.connect(websocket, "logs")
    last_count = 0
    try:
        while True:
            logs = await redis_service.get_critical_logs(limit=50)
            current_count = len(logs)

            if current_count != last_count:
                await websocket.send_json({"logs": logs})
                last_count = current_count

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "logs")
    except Exception:
        ws_manager.disconnect(websocket, "logs")
