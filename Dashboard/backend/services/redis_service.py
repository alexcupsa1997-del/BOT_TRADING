"""
Async Redis service for dashboard data access.
Reads keys exactly as published by mock_dashboard_data.py and live engine.
"""

import json
import redis.asyncio as aioredis
from typing import Optional

from config import settings


class RedisService:
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        self._client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        await self._client.ping()

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def is_connected(self) -> bool:
        try:
            await self.client.ping()
            return True
        except Exception:
            return False

    async def get_latency_ms(self) -> float:
        """Measure Redis round-trip latency."""
        import time
        start = time.monotonic()
        try:
            await self.client.ping()
            return (time.monotonic() - start) * 1000
        except Exception:
            return -1.0

    # ── System status ──────────────────────────────────────────────

    async def get_system_status(self) -> Optional[dict]:
        raw = await self.client.get(settings.redis_key_status)
        if raw:
            return json.loads(raw)
        return None

    # ── Trading data ───────────────────────────────────────────────

    async def get_orders(self) -> list[dict]:
        raw = await self.client.get(settings.redis_key_orders)
        if raw:
            return json.loads(raw)
        return []

    async def get_positions(self) -> list[dict]:
        raw = await self.client.get(settings.redis_key_positions)
        if raw:
            return json.loads(raw)
        return []

    async def get_equity_curve(self) -> list[dict]:
        raw = await self.client.get(settings.redis_key_equity_curve)
        if raw:
            return json.loads(raw)
        return []

    async def get_trade_history(self) -> list[dict]:
        raw = await self.client.get(settings.redis_key_trade_history)
        if raw:
            return json.loads(raw)
        return []

    # ── Logs ───────────────────────────────────────────────────────

    async def get_critical_logs(self, limit: int = 50) -> list[str]:
        logs = await self.client.lrange(settings.redis_key_logs, 0, limit - 1)
        return logs

    # ── Backtest status tracking ───────────────────────────────────

    async def set_backtest_status(self, run_id: str, status: str):
        await self.client.set(f"goliath:backtest:{run_id}", status, ex=86400)

    async def get_backtest_status(self, run_id: str) -> Optional[str]:
        return await self.client.get(f"goliath:backtest:{run_id}")

    # ── Config pub/sub ─────────────────────────────────────────────

    async def publish_config_update(self):
        await self.client.publish("goliath:config:updated", "reload")


redis_service = RedisService()
