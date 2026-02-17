"""
engine/strategy.py
==================

Strategy Base Class.
"""

import abc
import time
from decimal import Decimal
from typing import TYPE_CHECKING
from loguru import logger
from engine.events import Event, EventType

if TYPE_CHECKING:
    from engine.backtest_engine import BacktestEngine

class Strategy(abc.ABC):
    """Abstract Base Class for Strategies (Strategy Layer)."""

    def __init__(self, engine: 'BacktestEngine'):
        self.engine = engine
        self.position = Decimal("0")
        self.cash = Decimal("0")

    @abc.abstractmethod
    def on_start(self) -> None:
        """Called before the backtest loop starts."""
        pass

    @abc.abstractmethod
    def on_bar(self, event: Event) -> None:
        """Called on every new bar."""
        pass

    @abc.abstractmethod
    def on_fill(self, event: Event) -> None:
        """Called when an order is filled."""
        pass

    @abc.abstractmethod
    def on_stop(self) -> None:
        """Called after the backtest loop ends."""
        pass

    def buy(self, symbol: str, quantity: Decimal, price: Decimal) -> None:
        """Helper to submit a BUY order."""
        from engine.order import Order # lazy import to avoid circular dependency if any
        
        logger.info(f"Strategy requesting BUY {quantity} {symbol} @ {price}")
        order = Order(
            symbol=symbol,
            quantity=quantity,
            direction="BUY",
            price=price,
            timestamp=time.time()
        )
        
        order_event = Event(
            type=EventType.ORDER,
            data={"order": order}
        )
        self.engine.put(order_event)

    def sell(self, symbol: str, quantity: Decimal, price: Decimal) -> None:
        """Helper to submit a SELL order."""
        from engine.order import Order
        
        logger.info(f"Strategy requesting SELL {quantity} {symbol} @ {price}")
        order = Order(
            symbol=symbol,
            quantity=quantity,
            direction="SELL",
            price=price,
            timestamp=time.time()
        )
        
        order_event = Event(
            type=EventType.ORDER,
            data={"order": order}
        )
        self.engine.put(order_event)
