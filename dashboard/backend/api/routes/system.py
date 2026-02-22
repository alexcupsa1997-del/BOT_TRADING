"""
System monitoring endpoints.
GET /api/system/status  - Real-time system metrics
GET /api/system/services - Health of all services
"""

from fastapi import APIRouter

from services.redis_service import redis_service
from services import system_service, gateway_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def get_system_status():
    """Real-time system metrics from Redis + psutil."""
    # Try Redis first (data from mock_dashboard_data.py or real engine)
    status = await redis_service.get_system_status()

    if status is None:
        # Fallback: only psutil data
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

    # Supplement with fresh psutil data
    fresh = system_service.get_system_metrics()
    status["cpu_percent"] = fresh["cpu_percent"]
    status["ram_percent"] = fresh["ram_percent"]
    status["ram_mb"] = fresh["ram_mb"]
    status["disk_usage"] = fresh["disk_usage"]

    return {"data": status}


@router.get("/services")
async def get_services_health():
    """Check health of all external services."""
    redis_ok = await redis_service.is_connected()
    redis_latency = await redis_service.get_latency_ms()
    gateway_health = await gateway_service.check_gateway_health()
    analysis_health = await gateway_service.check_analysis_health()

    services = [
        {
            "name": "redis",
            "status": "ok" if redis_ok else "error",
            "latency_ms": round(redis_latency, 2),
        },
        {
            "name": "gateway",
            "status": gateway_health["status"],
            "details": gateway_health.get("details"),
        },
        {
            "name": "analysis",
            "status": analysis_health["status"],
            "details": analysis_health.get("details"),
        },
    ]

    return {"data": services}
