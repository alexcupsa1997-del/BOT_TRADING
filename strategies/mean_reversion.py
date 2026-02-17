"""
strategies/mean_reversion.py
============================

Mean Reversion Strategies.
"""

from decimal import Decimal
from engine.strategy import Strategy
from engine.events import Event
from engine.indicators import RSI
from loguru import logger

class RSIMeanReversionStrategy(Strategy):
    """
    RSI Mean Reversion.
    Buys when RSI < 30 (Oversold).
    Sells when RSI > 70 (Overbought).
    """
    
    def __init__(self, engine, period: int = 14, overbought: int = 70, oversold: int = 30):
        super().__init__(engine)
        self.rsi = RSI(period)
        self.overbought = Decimal(str(overbought))
        self.oversold = Decimal(str(oversold))
        self.invested = False

    def on_start(self) -> None:
        logger.info(f"Starting RSI Mean Reversion Strategy ({self.rsi.period}, OB={self.overbought}, OS={self.oversold})")

    def on_bar(self, event: Event) -> None:
        close_price = event.data["close"]
        symbol = event.data["symbol"]
        
        # Update Indicator
        rsi_val = self.rsi.update(close_price)
        
        if self.rsi.ready:
            # Buy Signal: Oversold
            if rsi_val < self.oversold and not self.invested:
                logger.info(f"OVERSOLD: RSI({rsi_val:.2f}) < {self.oversold}")
                qty = Decimal("0.1")
                self.buy(symbol, qty, close_price)
                self.invested = True
                
            # Sell Signal: Overbought
            elif rsi_val > self.overbought and self.invested:
                logger.info(f"OVERBOUGHT: RSI({rsi_val:.2f}) > {self.overbought}")
                qty = Decimal("0.1")
                self.sell(symbol, qty, close_price)
                self.invested = False

    def on_fill(self, event: Event) -> None:
        pass

    def on_stop(self) -> None:
        logger.info("Stopping RSI Mean Reversion Strategy")
