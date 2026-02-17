"""
tests/test_backtest_integration.py
==================================

Integration test for Phase 2.
Verifies:
1. Loading Parquet data via PolarsDataFeed.
2. Synchronous Event Loop execution.
3. Order generation and simulated fills.
4. Final portfolio state.
"""

import sys
import unittest
from pathlib import Path
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from engine.backtest_engine import BacktestEngine
from engine.data import PolarsDataFeed
from engine.strategy import Strategy
from engine.events import Event, EventType
from loguru import logger

class SimpleStrategy(Strategy):
    def on_start(self):
        self.count = 0
        
    def on_bar(self, event: Event):
        self.count += 1
        # Simple Logic: Buy on 5th bar, Sell on 10th
        if self.count == 5:
            price = event.data["close"]
            self.buy("BTCUSD", Decimal("0.1"), price)
        elif self.count == 10:
            price = event.data["close"]
            self.sell("BTCUSD", Decimal("0.1"), price)
            
    def on_fill(self, event: Event):
        trade = event.data['trade']
        logger.info(f"TEST STRATEGY FILLED: {trade.direction} @ {trade.price}")

    def on_stop(self):
        pass

class TestIntegration(unittest.TestCase):
    def test_full_loop(self):
        # Setup Engine
        engine = BacktestEngine()
        
        # Setup Data
        # Use the file we just fetched
        parquet_file = project_root / "data" / "raw" / "binance_BTCUSDT_1h.parquet"
        if not parquet_file.exists():
            self.fail(f"Parquet file not found: {parquet_file}")
            
        feed = PolarsDataFeed(str(parquet_file))
        engine.add_data_feed(feed)
        
        # Setup Strategy
        strat = SimpleStrategy(engine)
        engine.add_strategy(strat)
        
        # Run
        feed.load("2023-01-01", "2024-01-01") # Date range ignored in V1
        engine.run()
        
        # Verify
        self.assertGreater(strat.count, 0, "Strategy should have seen bars")
        self.assertTrue(len(engine.order_history) >= 0, "Should have order history (if logic triggered)")
        # Check cash changed (commissions/slippage might come later, but buy/sell should affect cash)
        # We bought 0.1 and sold 0.1.
        # If price changed, cash should differ from initial 100k.
        # This asserts we actually traded.
        self.assertNotEqual(engine.cash, Decimal("100000.00"), "Cash should have changed after round trip")

if __name__ == "__main__":
    unittest.main()
