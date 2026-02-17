"""
tests/test_strategies.py
========================

Unit tests for strategies.
"""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock
from engine.events import Event, EventType
from strategies.trend import SMACrossoverStrategy
from strategies.mean_reversion import RSIMeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.grid import SimpleGridStrategy

class TestStrategies(unittest.TestCase):
    
    def setUp(self):
        self.mock_engine = MagicMock()
        self.mock_engine.put = MagicMock()

    def test_sma_crossover(self):
        # Fast=3, Slow=5 for testing
        strat = SMACrossoverStrategy(self.mock_engine, fast_period=3, slow_period=5)
        strat.on_start()
        
        prices = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11]
        # SMA3: -, -, 11, 12, 13, 14, 14, 13.3, 13, 12
        # SMA5: -, -, -, -, 12, 13, 13.8, 13.8, 13.6, 13
        
        # Ticks:
        # 1. 10
        # 2. 11
        # 3. 12 (SMA3=11)
        # 4. 13 (SMA3=12)
        # 5. 14 (SMA3=13, SMA5=12). CROSSOVER! 13 > 12. BUY.
        # 6. 15 (SMA3=14, SMA5=13). 14 > 13. Hold.
        
        for p in prices:
            evt = Event(EventType.BAR, {
                "symbol": "BTC", 
                "close": Decimal(p), 
                "timestamp": 1000
            })
            strat.on_bar(evt)
            
        # Check if buy was called
        # At price 14 (idx 4), Fast=13, Slow=12. Golden Cross.
        # self.mock_engine.put should be called with ORDER BUY
        
        # Verify calls
        calls = self.mock_engine.put.call_args_list
        self.assertTrue(len(calls) > 0, "Should have triggered a trade")
        
        # First call should be BUY
        first_call = calls[0]
        event = first_call[0][0]
        self.assertEqual(event.type, EventType.ORDER)
        self.assertEqual(event.data["direction"], "BUY")
        self.assertEqual(event.data["price"], Decimal("14"))

    def test_rsi_mean_reversion(self):
        # Period=3 for testing
        strat = RSIMeanReversionStrategy(self.mock_engine, period=3, overbought=70, oversold=30)
        strat.on_start()
        
        # Create a sequence that drives RSI down then up
        # Drop: 100, 90, 80, 70, 60
        # Gains: 0, 0, 0, 0
        # Losses: 10, 10, 10, 10
        # AvgLoss will be high, RSI low.
        
        prices = [100, 90, 80, 70, 60, 50, 40, 30] 
        # Changes: -10, -10, -10, -10, -10, -10, -10
        # Period 3.
        # 1. 100
        # 2. 90 (chg -10)
        # 3. 80 (chg -10)
        # 4. 70 (chg -10). AvgGain=0, AvgLoss=10. RS=0. RSI=0. 0 < 30. BUY.
        
        for p in prices:
            evt = Event(EventType.BAR, {
                "symbol": "BTC",
                "close": Decimal(p),
                "timestamp": 1000
            })
            strat.on_bar(evt)
            
        calls = self.mock_engine.put.call_args_list
        self.assertTrue(len(calls) > 0, "Should have triggered a trade")
        
        first_call = calls[0]
        event = first_call[0][0]
        self.assertEqual(event.type, EventType.ORDER)
        self.assertEqual(event.data["direction"], "BUY")      

    def test_breakout_strategy(self):
        # Period=20, StdDev=2
        # Need N > K^2 + 1 to trigger breakout on single spike from flat.
        # 20 > 5. OK.
        strat = BreakoutStrategy(self.mock_engine, period=20, std_dev=2, quantity=0.1)
        # strat.engine = self.mock_engine # Already passed in init
        strat.on_start()
        
        # Upper band = SMA + 2*StdDev
        
        prices = [10] * 20
        # Ready. Upper=10.
        
        for p in prices:
            evt = Event(EventType.BAR, {
                "symbol": "BTC",
                "close": Decimal(p),
                "timestamp": 1000
            })
            strat.on_bar(evt)
            
        # Now inject breakout
        evt = Event(EventType.BAR, {
            "symbol": "BTC", 
            "close": Decimal("10.5"), 
            "timestamp": 1001
        })
        strat.on_bar(evt)
        # 10.5 > 10.1 (Upper Band). Breakout UP. BUY.
        
        calls = self.mock_engine.put.call_args_list
        self.assertTrue(len(calls) > 0, "Should have triggered Breakout BUY")
        evt = calls[0][0][0]
        self.assertEqual(evt.data["direction"], "BUY")

    def test_grid_strategy(self):
        # Grid Step=10.
        strat = SimpleGridStrategy(self.mock_engine, grid_step=10, quantity=0.1)
        # strat.engine = self.mock_engine
        strat.on_start()
        
        # Price 100. Level=100.
        evt1 = Event(EventType.BAR, {"symbol": "BTC", "close": Decimal(100), "timestamp": 1000})
        strat.on_bar(evt1)
        
        # Price 95. Level=100 (95/10 = 9.5 -> 10 * 10 = 100). No change.
        evt2 = Event(EventType.BAR, {"symbol": "BTC", "close": Decimal(96), "timestamp": 1001})
        strat.on_bar(evt2)
        
        # Price 89. Level=90. (89/10 = 8.9 -> 9 * 10 = 90).
        # Previous 100. Current 90. 90 < 100. GRID DOWN. BUY.
        evt3 = Event(EventType.BAR, {"symbol": "BTC", "close": Decimal(89), "timestamp": 1002})
        strat.on_bar(evt3)
        
        calls = self.mock_engine.put.call_args_list
        self.assertTrue(len(calls) > 0, "Should have triggered Grid BUY")
        evt = calls[0][0][0]
        self.assertEqual(evt.data["direction"], "BUY")

if __name__ == "__main__":
    unittest.main()
