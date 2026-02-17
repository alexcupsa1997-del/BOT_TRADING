"""
strategies/breakout.py
======================

Volatility Breakout Strategy.
Uses Bollinger Bands to identify breakouts.

Logic:
    - Close > Upper Band -> BUY (Breakout Up)
    - Close < Lower Band -> SELL (Breakout Down)
    - Optional: Stop Loss / Take Profit managed by Risk Manager, or logic here.
      For this basic version, we reverse on opposite signal.
"""

from decimal import Decimal
from engine.strategy import Strategy
from engine.events import Event, EventType
from engine.indicators import BollingerBands
from loguru import logger

class BreakoutStrategy(Strategy):
    """
    Volatility Breakout Strategy using Bollinger Bands.
    """

    def __init__(self, engine, period: int = 20, std_dev: int = 2, quantity: float = 0.1):
        super().__init__(engine)
        self.bb = BollingerBands(period, std_dev)
        self.quantity = Decimal(str(quantity))
        self.position = 0 # 1 = Long, -1 = Short, 0 = Neutral
        
        logger.info(f"Starting Breakout Strategy ({period}, {std_dev})")

    def on_start(self):
        pass

    def on_stop(self):
        pass

    def on_bar(self, event: Event):
        # Update Indicators
        close_price = Decimal(str(event.data['close']))
        self.bb.update(close_price)

        if not self.bb.ready:
            return

        # Logic
        upper = self.bb.upper
        lower = self.bb.lower

        if close_price > upper:
            logger.info(f"BREAKOUT UP: {close_price} > {upper}")
            if self.position <= 0:
                self.buy(event.data['symbol'], self.quantity, close_price)
                self.position = 1

        elif close_price < lower:
            logger.info(f"BREAKOUT DOWN: {close_price} < {lower}")
            if self.position >= 0:
                self.sell(event.data['symbol'], self.quantity, close_price)
                self.position = -1

    def on_fill(self, event: Event):
        """
        Callback for order fill events.
        """
        logger.info(f"Breakout Order Filled: {event.data}")
