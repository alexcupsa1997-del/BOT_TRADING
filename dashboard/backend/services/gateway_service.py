"""
HTTP client to communicate with the Go gateway and analysis signal server.
"""

import httpx
from typing import Optional

from config import settings


async def check_gateway_health() -> dict:
    """Check Go gateway health at /health."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.gateway_url}/health")
            if resp.status_code == 200:
                return {"status": "ok", "data": resp.json()}
            return {"status": "error", "details": f"HTTP {resp.status_code}"}
    except httpx.ConnectError:
        return {"status": "unreachable", "details": "Connection refused"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def check_analysis_health() -> dict:
    """Check analysis signal server health."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.analysis_url}/health")
            if resp.status_code == 200:
                return {"status": "ok"}
            return {"status": "error", "details": f"HTTP {resp.status_code}"}
    except httpx.ConnectError:
        return {"status": "unreachable", "details": "Connection refused"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def get_signal(symbol: str, timeframe: str = "H1") -> Optional[dict]:
    """Fetch ML signal from gateway (which proxies to analysis server)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.gateway_url}/api/signal/{symbol}",
                params={"timeframe": timeframe},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None
