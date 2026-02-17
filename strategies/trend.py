"""
strategies/trend.py
===================

Trend Following Strategies.
"""

from decimal import Decimal
from engine.strategy import Strategy
from engine.events import Event, EventType
from engine.indicators import SMA
from loguru import logger

class SMACrossoverStrategy(Strategy):
    """
    Golden Cross / Death Cross Strategy.
    Buys when Fast SMA > Slow SMA.
    Sells when Fast SMA < Slow SMA.
    """
    
    def __init__(self, engine, fast_period: int = 50, slow_period: int = 200):
        super().__init__(engine)
        self.fast_sma = SMA(fast_period)
        self.slow_sma = SMA(slow_period)
        self.invested = False

    def on_start(self) -> None:
        logger.info(f"Starting SMA Crossover Strategy ({self.fast_sma.period}/{self.slow_sma.period})")

    def on_bar(self, event: Event) -> None:
        close_price = event.data["close"]
        symbol = event.data["symbol"]
        
        # Update Indicators
        fast_val = self.fast_sma.update(close_price)
        slow_val = self.slow_sma.update(close_price)
        
        # Trading Logic
        if self.fast_sma.ready and self.slow_sma.ready:
            
            # Buy Signal: Fast crosses above Slow
            if fast_val > slow_val and not self.invested:
                logger.info(f"GOLDEN CROSS: Fast({fast_val}) > Slow({slow_val})")
                qty = Decimal("0.1") # Fixed size for now
                self.buy(symbol, qty, close_price)
                self.invested = True
                
            # Sell Signal: Fast crosses below Slow
            elif fast_val < slow_val and self.invested:
                logger.info(f"DEATH CROSS: Fast({fast_val}) < Slow({slow_val})")
                qty = Decimal("0.1")
                self.sell(symbol, qty, close_price)
                self.invested = False

    def on_fill(self, event: Event) -> None:
        # In a real strategy, we'd update position state here based on fill confirmation
        # For this simple example, we assume fill happens if generic engine logic works
        pass

    def on_stop(self) -> None:
        logger.info("Stopping SMA Crossover Strategy")
