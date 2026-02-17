"""
engine/fill_simulator.py - Order Execution Simulation
=====================================================

Simulates exchange execution logic (fills, slippage, fees) for backtesting.
Based on the Fusion Plan architecture to decouple simulation from the core engine.
"""

from decimal import Decimal
from typing import Dict, Optional
from loguru import logger
import time

from engine.events import Event, EventType

class FillSimulator:
    """
    Simulates order execution based on current market data.
    Supports:
    - Market Orders (Instant fill at current price)
    - Limit Orders (Fill if price crosses limit) - TODO
    - Slippage Model - TODO
    - Fee Calculation - TODO
    """

    def __init__(self):
        pass

    def process_order(self, order_event: Event) -> Optional[Event]:
        """
        Process an ORDER event (containing Order object) and generate a FILL event (containing Trade object).
        """
        if order_event.type != EventType.ORDER:
            return None
            
        # Unpack Order
        from engine.order import Order, Trade
        order: Order = order_event.data.get("order")
        if not order:
            logger.error("Received ORDER event without 'order' data")
            return None

        # Simulation Logic
        # For Market Orders Main Assumption: executed at requested price (simplified)
        exec_price = order.price if order.price else Decimal("0") # TODO: Get from market data
        
        cost = order.quantity * exec_price
        
        logger.debug(f"Simulating fill for {order.symbol}: {order.direction} {order.quantity} @ {exec_price}")
        
        trade = Trade(
            symbol=order.symbol,
            quantity=order.quantity,
            price=exec_price,
            direction=order.direction,
            cost=cost,
            order_id=order.id,
            timestamp=order.timestamp # Simulated time
        )
        
        fill_event = Event(
            type=EventType.FILL,
            data={"trade": trade}
        )
        return fill_event
