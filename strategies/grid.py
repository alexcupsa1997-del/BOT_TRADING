"""
strategies/grid.py
==================

Simple Grid Strategy.
Places buy/sell orders at fixed intervals around a reference price.

Logic:
    - Define Grid Lines (e.g., every 100 USDT).
    - If Price crosses line UP -> SELL (Take Profit / Counter Trend) or BUY (Trend)?
    - Standard Grid: Buy Low, Sell High.
      - If Price drops to Level X, Buy.
      - If Price rises to Level X+Step, Sell.
    
    For this implementation:
    - Dynamic Grid based on initial price.
    - Buy limit orders below.
    - Sell limit orders above.
    
    *Simplified for Event-Driven Backtest*:
    - Since we don't have Limit Order support in the basic engine fully tested yet (we do have types, but FillSimulator is basic),
      we will simulate "Market" entries when price crosses grid levels.
"""

from decimal import Decimal
from engine.strategy import Strategy
from engine.events import Event, EventType
from loguru import logger
import math

class SimpleGridStrategy(Strategy):
    """
    Simple Grid Strategy.
    Buys at checks below, Sells at checks above.
    """

    def __init__(self, engine, grid_step: float = 100.0, quantity: float = 0.01):
        super().__init__(engine)
        self.step = Decimal(str(grid_step))
        self.quantity = Decimal(str(quantity))
        self.last_grid_level = None
        
        logger.info(f"Starting Grid Strategy (Step={grid_step})")

    def on_start(self):
        pass

    def on_stop(self):
        pass

    def on_bar(self, event: Event):
        close_price = Decimal(str(event.data['close']))
        
        # Determine current grid level
        # Level = round(Price / Step) * Step
        current_level = (close_price / self.step).quantize(Decimal("1.")) * self.step
        
        if self.last_grid_level is None:
            self.last_grid_level = current_level
            return

        # If we moved to a new level
        if current_level != self.last_grid_level:
            if current_level < self.last_grid_level:
                # Price dropped to lower level -> BUY
                logger.info(f"GRID DOWN: {self.last_grid_level} -> {current_level} | BUY")
                self.buy(event.data['symbol'], self.quantity, close_price)
            
            elif current_level > self.last_grid_level:
                # Price rose to higher level -> SELL
                logger.info(f"GRID UP: {self.last_grid_level} -> {current_level} | SELL")
                self.sell(event.data['symbol'], self.quantity, close_price)
            
            self.last_grid_level = current_level

    def on_fill(self, event: Event):
        """
        Callback for order fill events.
        """
        logger.info(f"Grid Order Filled: {event.data}")
