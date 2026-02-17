"""
engine/order.py
===============

Domain models for Orders and Trades.
"""

import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

@dataclass
class Order:
    symbol: str
    quantity: Decimal
    direction: str  # "BUY" or "SELL"
    order_type: str = "MARKET"  # "MARKET", "LIMIT", "STOP"
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    status: str = "PENDING"  # "PENDING", "FILLED", "CANCELLED", "REJECTED"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        # Ensure Decimal precision
        if isinstance(self.quantity, (float, int, str)):
            self.quantity = Decimal(str(self.quantity))
        if self.price is not None and isinstance(self.price, (float, int, str)):
            self.price = Decimal(str(self.price))

@dataclass
class Trade:
    symbol: str
    quantity: Decimal
    price: Decimal
    direction: str
    cost: Decimal
    commission: Decimal = Decimal("0.0")
    order_id: str = ""
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if isinstance(self.quantity, (float, int, str)):
            self.quantity = Decimal(str(self.quantity))
        if isinstance(self.price, (float, int, str)):
            self.price = Decimal(str(self.price))
        if isinstance(self.cost, (float, int, str)):
            self.cost = Decimal(str(self.cost))
