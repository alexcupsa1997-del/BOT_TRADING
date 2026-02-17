"""
engine/portfolio.py - Portfolio Management
==========================================

Tracks cash, positions, and equity.
Used by both BacktestEngine (eventually) and LiveEngine.
"""

from decimal import Decimal
from typing import Dict, Optional
from loguru import logger
from engine.order import Trade

class PortfolioManager:
    def __init__(self, initial_cash: Decimal = Decimal("10000.0")):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: Dict[str, Decimal] = {}
        self.equity = initial_cash
        self.pnl = Decimal("0.0")

    def on_fill(self, trade: Trade) -> None:
        """Updates portfolio state based on a filled trade."""
        cost = trade.cost
        qty = trade.quantity
        symbol = trade.symbol
        
        if trade.direction == "BUY":
            if self.cash >= cost:
                self.cash -= cost
                self.positions[symbol] = self.positions.get(symbol, Decimal("0")) + qty
                logger.info(f"PORTFOLIO: Bought {qty} {symbol}. Cash: {self.cash:.2f}")
            else:
                logger.error(f"PORTFOLIO: Insufficient cash for BUY {symbol} (Need {cost}, Have {self.cash})")
                
        elif trade.direction == "SELL":
            current_qty = self.positions.get(symbol, Decimal("0"))
            if current_qty >= qty:
                self.cash += cost
                self.positions[symbol] = current_qty - qty
                logger.info(f"PORTFOLIO: Sold {qty} {symbol}. Cash: {self.cash:.2f}")
            else:
                logger.warning(f"PORTFOLIO: Insufficient quantity for SELL {symbol} (Need {qty}, Have {current_qty})")

    def update_equity(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """Recalculates total equity based on current market prices."""
        equity = self.cash
        for symbol, qty in self.positions.items():
            price = current_prices.get(symbol, Decimal("0"))
            equity += qty * price
            
        self.equity = equity
        self.pnl = self.equity - self.initial_cash
        return self.equity

    def get_position(self, symbol: str) -> Decimal:
        return self.positions.get(symbol, Decimal("0"))
