"""
CLI Runner — Entry point for paper trading.

Usage:
    PYTHONPATH=. python -m src.execution.runner --symbol BTC/USDT --timeframe 1h
    PYTHONPATH=. python -m src.execution.runner --symbol XAUUSD --timeframe 1h --balance 5000

Ref: FUSION_PLAN Fase 6
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

from loguru import logger

from src.execution.paper_trader import PaperTradingConfig, PaperTradingHarness
from src.orchestrator import TradingOrchestrator, OrchestratorConfig
from src.integration.exchange_manager import ExchangeManager
from src.integration.config import ExchangeConfig
from src.integration.notifier import Notifier, NotifierConfig
from src.quant.risk_manager import RiskConfig


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GOLIATH Paper Trading Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--symbol", default="BTC/USDT", help="Trading pair")
    parser.add_argument("--timeframe", default="1h", help="OHLCV timeframe")
    parser.add_argument("--balance", type=float, default=10000.0,
                        help="Initial paper balance")
    parser.add_argument("--poll", type=float, default=60.0,
                        help="Poll interval in seconds")
    parser.add_argument("--min-confidence", type=float, default=0.65,
                        help="Minimum signal confidence")
    parser.add_argument("--max-drawdown", type=float, default=0.15,
                        help="Max drawdown before halt (fraction)")
    parser.add_argument("--exchange", default="binance",
                        help="CCXT exchange ID")
    parser.add_argument("--sandbox", action="store_true",
                        help="Use exchange sandbox/testnet")
    parser.add_argument("--monte-carlo", action="store_true",
                        help="Run Monte Carlo analysis after paper run")
    return parser.parse_args()


def build_harness(args: argparse.Namespace) -> PaperTradingHarness:
    """Assemble the full paper trading harness from CLI args + env vars."""
    # Exchange
    exchange_config = ExchangeConfig(
        exchange_id=args.exchange,
        sandbox=args.sandbox or True,  # Paper trading always sandbox
        api_key=os.getenv("GOLIATH_API_KEY"),
        secret=os.getenv("GOLIATH_API_SECRET"),
    )
    exchange = ExchangeManager(exchange_config)

    # Map CCXT timeframe to orchestrator timeframe
    tf_map = {
        "1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30",
        "1h": "H1", "4h": "H4", "1d": "D1",
    }
    goliath_tf = tf_map.get(args.timeframe, "H1")

    # Paper trading config
    pt_config = PaperTradingConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        goliath_timeframe=goliath_tf,
        poll_interval_seconds=args.poll,
        min_confidence=args.min_confidence,
        initial_balance=Decimal(str(args.balance)),
        max_drawdown_pct=args.max_drawdown,
    )

    # Orchestrator
    notifier_config = NotifierConfig.from_env()
    orchestrator = TradingOrchestrator(OrchestratorConfig(
        notifier_config=notifier_config,
    ))

    # Notifier
    notifier = Notifier(notifier_config)

    # Risk config
    risk_config = RiskConfig(
        initial_balance=args.balance,
        max_drawdown=args.max_drawdown,
        max_daily_risk=0.05,
        max_concurrent_positions=1,
    )

    return PaperTradingHarness(
        config=pt_config,
        exchange=exchange,
        orchestrator=orchestrator,
        notifier=notifier,
        risk_config=risk_config,
    )


async def main_async(args: argparse.Namespace) -> None:
    """Run paper trading and optional post-run analysis."""
    harness = build_harness(args)

    logger.info(f"Starting paper trading: {args.symbol} / {args.timeframe}")
    logger.info(f"Balance: {args.balance} | Max DD: {args.max_drawdown:.0%}")

    try:
        await harness.run()
    except KeyboardInterrupt:
        harness.stop()
        logger.info("Interrupted by user")

    # Post-run analysis
    journal = harness.get_journal()
    logger.info(f"Paper run complete: {len(journal)} trades")

    if args.monte_carlo and len(journal) >= 5:
        from src.quant.monte_carlo import MonteCarloSimulator
        sim = MonteCarloSimulator(journal)
        report = sim.format_report()
        logger.info(f"\n{report}")


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
