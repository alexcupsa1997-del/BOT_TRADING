"""
GOLIATH Dashboard Backend - FastAPI Application
================================================
Port: 8888 (avoids conflicts with analysis:8000, gateway:8080)
Run:  uvicorn main:app --host 0.0.0.0 --port 8888 --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from services.redis_service import redis_service
from api.routes import system, trading, backtest, config_routes, logs, market, ml
from ws import streams


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to Redis
    try:
        await redis_service.connect()
        print(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        print(f"WARNING: Redis connection failed: {e}")
        print("Dashboard will run with limited functionality (psutil-only metrics)")

    yield

    # Shutdown: close connections
    await redis_service.disconnect()
    print("Redis disconnected. Dashboard shutting down.")


app = FastAPI(
    title="GOLIATH Dashboard API",
    description="Backend API for the GOLIATH Trading Bot Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routes
app.include_router(system.router)
app.include_router(trading.router)
app.include_router(backtest.router)
app.include_router(config_routes.router)
app.include_router(logs.router)
app.include_router(market.router)
app.include_router(ml.router)

# WebSocket routes
app.include_router(streams.router)


@app.get("/")
async def root():
    return {
        "name": "GOLIATH Dashboard API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "system": "/api/system/status",
            "trading": "/api/trading/status",
            "backtest": "/api/backtest/list",
            "config": "/api/config",
            "logs": "/api/logs/critical",
            "market": "/api/market/files",
            "ml": "/api/ml/model-info",
            "ws_status": "ws://localhost:8888/ws/status",
            "ws_trading": "ws://localhost:8888/ws/trading",
            "ws_logs": "ws://localhost:8888/ws/logs",
        },
    }


@app.get("/health")
async def health():
    redis_ok = await redis_service.is_connected()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
    }
