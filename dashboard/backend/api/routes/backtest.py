"""
Backtest management endpoints.
POST /api/backtest/run         - Launch a new backtest
GET  /api/backtest/status/{id} - Check backtest status
GET  /api/backtest/results/{id} - Get completed results
GET  /api/backtest/list        - List all past runs
"""

import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor
from fastapi import APIRouter, HTTPException

from config import settings
from models.schemas import BacktestRequest
from services.redis_service import redis_service

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

_executor = ProcessPoolExecutor(max_workers=2)


def _run_backtest_sync(run_id: str, config: dict) -> dict:
    """Run backtest in a separate process. Returns result dict."""
    import sys
    sys.path.insert(0, config["project_root"])

    from decimal import Decimal
    from engine.backtest_engine import BacktestEngine
    from engine.data import PolarsDataFeed
    from engine.reporting import PerformanceReport

    data_path = Path(config["project_root"]) / config["data_file"]
    if not data_path.exists():
        return {"run_id": run_id, "status": "failed", "error": f"Data file not found: {data_path}"}

    try:
        feed = PolarsDataFeed(str(data_path), config["symbol"])
        initial_cash = Decimal(config["initial_cash"])
        engine = BacktestEngine(feed, initial_cash=initial_cash)
        engine.run()

        report = PerformanceReport(engine.history, initial_capital=initial_cash)
        metrics = report.summary()

        # Serialize equity curve (convert Decimal to str)
        equity_curve = []
        for point in engine.history:
            equity_curve.append({
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in point.items()
            })

        return {
            "run_id": run_id,
            "status": "completed",
            "params": {
                "data_file": config["data_file"],
                "symbol": config["symbol"],
                "initial_cash": config["initial_cash"],
                "strategy": config.get("strategy", "default"),
            },
            "metrics": {k: str(v) for k, v in metrics.items()} if metrics else {},
            "equity_curve": equity_curve,
        }
    except Exception as e:
        return {"run_id": run_id, "status": "failed", "error": str(e)}


async def _run_backtest_task(run_id: str, config: dict):
    """Background task to run backtest and store results."""
    await redis_service.set_backtest_status(run_id, "running")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _run_backtest_sync, run_id, config)

    # Save result to file
    results_dir = Path(settings.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / f"{run_id}.json"

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    await redis_service.set_backtest_status(run_id, result["status"])


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """Launch a new backtest run."""
    run_id = str(uuid.uuid4())[:8]

    config = {
        "project_root": settings.project_root,
        "data_file": req.data_file,
        "symbol": req.symbol,
        "initial_cash": req.initial_cash,
        "strategy": req.strategy,
        "strategy_params": req.strategy_params,
    }

    # Fire and forget the background task
    asyncio.create_task(_run_backtest_task(run_id, config))

    return {
        "data": {
            "run_id": run_id,
            "status": "running",
            "message": f"Backtest {run_id} started",
        }
    }


@router.get("/status/{run_id}")
async def get_backtest_status(run_id: str):
    """Check status of a backtest run."""
    status = await redis_service.get_backtest_status(run_id)
    if status is None:
        # Check if result file exists
        result_path = Path(settings.results_dir) / f"{run_id}.json"
        if result_path.exists():
            status = "completed"
        else:
            raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")

    return {"data": {"run_id": run_id, "status": status}}


@router.get("/results/{run_id}")
async def get_backtest_results(run_id: str):
    """Get results of a completed backtest."""
    result_path = Path(settings.results_dir) / f"{run_id}.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail=f"Results for {run_id} not found")

    with open(result_path, "r") as f:
        result = json.load(f)

    return {"data": result}


@router.get("/list")
async def list_backtests():
    """List all past backtest runs."""
    results_dir = Path(settings.results_dir)
    if not results_dir.exists():
        return {"data": []}

    runs = []
    for f in sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, "r") as fp:
                data = json.load(fp)
            runs.append({
                "run_id": data.get("run_id", f.stem),
                "status": data.get("status", "unknown"),
                "symbol": data.get("params", {}).get("symbol", "N/A"),
                "strategy": data.get("params", {}).get("strategy", "N/A"),
                "created_at": datetime.fromtimestamp(
                    f.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        except Exception:
            continue

    return {"data": runs}
