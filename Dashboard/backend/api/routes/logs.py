"""
Log viewing endpoints.
GET /api/logs/critical - Critical logs from Redis
GET /api/logs/engine   - Engine log file tail
GET /api/logs/files    - List available log files
"""

from fastapi import APIRouter, Query

from services.redis_service import redis_service
from services import log_service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/critical")
async def get_critical_logs(limit: int = Query(50, ge=1, le=500)):
    """Fetch recent critical logs from Redis."""
    logs = await redis_service.get_critical_logs(limit=limit)
    return {"data": logs}


@router.get("/engine")
async def get_engine_logs(
    filename: str = Query(None, description="Specific log file name"),
    lines: int = Query(100, ge=1, le=1000),
):
    """Read last N lines from engine log file."""
    log_lines = log_service.read_log_file(filename=filename, lines=lines)
    return {"data": log_lines}


@router.get("/files")
async def list_log_files():
    """List available log files."""
    files = log_service.list_log_files()
    return {"data": files}
