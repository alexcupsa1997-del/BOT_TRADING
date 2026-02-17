"""
backtest_engine.py - Event-Driven Backtesting Core (Phase 2)
===========================================================

This module implements the core event loop for GOLIATH's backtesting engine.
Refactored to use modular components:
    - engine.events: Event definitions
    - engine.fill_simulator: Execution logic
    - engine.data: Data Feed interfaces
    - engine.strategy: Strategy interfaces

Author: GOLIATH Team
Date: 2026-02-15
"""

import sys
import abc
import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from typing import Any, Callable, Dict, List, Optional, Protocol, Union

# Third-party imports
from loguru import logger

# Internal imports
from engine.events import Event, EventType
from engine.fill_simulator import FillSimulator
from engine.reporting import PerformanceReport
from engine.data import DataFeed
from engine.strategy import Strategy
from engine.order import Order, Trade

# Set strict decimal precision
getcontext().prec = 28

# --- The Engine ---

class BacktestEngine:
    """
    Synchronous Event Engine for Backtesting.
    """

    def __init__(self, initial_cash: Decimal = Decimal("100000.0"), verbose: bool = True):
        self.data_feeds: List[DataFeed] = []
        self.strategies: List[Strategy] = []
        self.handlers: Dict[EventType, List[Callable]] = {t: [] for t in EventType}
        self.queue: deque = deque()
        self.active: bool = False
        self.verbose = verbose
        
        # Portfolio State
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.portfolio: Dict[str, Decimal] = {}
        self.history: List[Dict[str, Any]] = [] # Consolidated history initialization
        self.last_prices: Dict[str, Decimal] = {} # Consolidated last_prices initialization
        self.current_time: Any = None

        # Components
        self.fill_simulator = FillSimulator()

    def register_handler(self, event_type: EventType, handler: Callable) -> None:
        self.handlers[event_type].append(handler)

    def add_data_feed(self, feed: DataFeed) -> None:
        self.data_feeds.append(feed)

    def add_strategy(self, strategy: Strategy) -> None:
        self.strategies.append(strategy)
        self.register_handler(EventType.BAR, strategy.on_bar)
        self.register_handler(EventType.FILL, strategy.on_fill)

    def put(self, event: Event) -> None:
        self.queue.append(event)

    def _update_equity(self, timestamp: int):
        equity = self.cash
        for symbol, qty in self.portfolio.items():
            price = self.last_prices.get(symbol, Decimal("0"))
            equity += qty * price
        
        self.history.append({
            "timestamp": timestamp,
            "total_equity": equity,
            "cash": self.cash
        })

    def _process_event(self, event: Event) -> None:
        # Update Market Data State
        if event.type == EventType.BAR:
            data = event.data
            self.last_prices[data['symbol']] = data['close']
            self._update_equity(data['timestamp'])

        # 1. Order Processing (Simulation)
        if event.type == EventType.ORDER:
            fill_event = self.fill_simulator.process_order(event)
            if fill_event:
                self._handle_fill(fill_event)
        
        # 2. Strategy Handling
        if event.type in self.handlers:
            for handler in self.handlers[event.type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in handler {handler.__name__}: {e}")

    def _handle_fill(self, event: Event) -> None:
        """Update portfolio state on fill (Trade object)."""
        from engine.order import Trade
        trade: Trade = event.data.get("trade")
        if not trade:
            return

        qty = trade.quantity
        cost = trade.cost
        direction = trade.direction
        symbol = trade.symbol
        price = trade.price
        
        if direction == "BUY":
            if self.cash >= cost:
                self.cash -= cost
                self.portfolio[symbol] = self.portfolio.get(symbol, Decimal("0")) + qty
                logger.success(f"FILLED BUY: {qty} {symbol} @ {price}. Cash: {self.cash}")
                # Notify Strategies
                for strat in self.strategies:
                    strat.on_fill(event)
            else:
                logger.warning(f"Simulated Fill Rejected: Insufficient Cash {self.cash} < {cost}")
        
        elif direction == "SELL":
            curr = self.portfolio.get(symbol, Decimal("0"))
            if curr >= qty:
                self.cash += cost
                self.portfolio[symbol] = curr - qty
                logger.success(f"FILLED SELL: {qty} {symbol} @ {price}. Cash: {self.cash}")
                # Notify Strategies
                for strat in self.strategies:
                    strat.on_fill(event)
            else:
                 logger.warning(f"Simulated Fill Rejected: Insufficient Qty {curr} < {qty}")

    def run(self) -> 'PerformanceReport':
        """
        Run the Backtest Loop:
        1. Initialize Strategies
        2. Stream Data
        3. Process Events
        4. Generate Report
        """
        if self.verbose:
            logger.info("Backtest Engine Started.")
        
        for strat in self.strategies:
            strat.on_start()
            
        if not self.data_feeds:
            logger.error("No data feeds attached!")
            return

        main_feed = self.data_feeds[0]
        
        # Initial Primer
        event = main_feed.get_next()
        if event:
            self.queue.append(event)
            
        while self.queue or event is not None:
             if not self.queue:
                 event = main_feed.get_next()
                 if event is None:
                     break
                 self.queue.append(event)
            
             event = self.queue.popleft()
             
             if event.data and "timestamp" in event.data:
                  self.current_time = event.data["timestamp"]
             
             # Process
             self._process_event(event)
            
        for strat in self.strategies:
            strat.on_stop()
            
        if self.verbose:
            logger.info("Backtest Engine Finished.")
        
        # Calculate Final Equity
        # ... logic to mark to market open positions ...
        
        final_equity = self.history[-1]['total_equity'] if self.history else self.cash
        if self.verbose:
            logger.info(f"Final Equity: {final_equity}")

        # Generate Report
        report = PerformanceReport(self.history, self.initial_cash)
        if self.verbose:
            report.print_report()
        
        return report
