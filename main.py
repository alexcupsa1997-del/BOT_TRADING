"""
main.py - GOLIATH Entry Point
=============================

Launches the Trading Engine in the specified mode (Paper/Live).
"""

import sys
import os
import json
import time
import signal
from decimal import Decimal
from loguru import logger

# Ensure project root is in path
sys.path.append(os.getcwd())

from engine.events import Event, EventType
from engine.data import DataFeed
from engine.live_feed import RealTimeDataFeed
from engine.execution import SimulatedExecutionHandler, CCXTExecutionHandler
from engine.portfolio import PortfolioManager
# from strategies.ml_strategy import MLStrategy # TODO: Enable when model is ready
from strategies.trend import Header, SMAStrategy # Fallback for now

class LiveEngine:
    def __init__(self, config_path: str):
        self.active = False
        self.queue = [] # Simple list for now, or deque
        
        # Load Config
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        logger.add(self.config['logging']['file'], level=self.config['logging']['level'])
        logger.info(f"Initializing GOLIATH in {self.config['mode']} mode...")
        
        # Components
        self.portfolio = PortfolioManager(initial_cash=Decimal(str(self.config['balance'])))
        
        # Feed
        self.feed = RealTimeDataFeed(
            exchange_id='binance', 
            symbol=self.config['symbols'][0].replace("USD", "/USDT"), # Simple mapping
            timeframe=self.config['timeframe']
        )
        
        # Strategy (Placeholder until ML Strategy checks out)
        # self.strategy = MLStrategy(model_path=self.config['strategy']['model_path'])
        self.strategy = SMAStrategy(fast_period=10, slow_period=20) 
        
        # Execution
        if self.config['mode'] == 'live':
             # TODO: Load keys from secure env
             self.execution = CCXTExecutionHandler('binance', 'api_key', 'api_secret', sandbox=False)
        else:
             self.execution = SimulatedExecutionHandler(self)
             
    def run(self):
        self.active = True
        logger.info("Engine Started. Press Ctrl+C to stop.")
        
        # Signal handling
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        
        self.feed.load() # Warmup
        
        while self.active:
            try:
                # 1. Get Market Data (Blocking/Polling)
                event = self.feed.get_next()
                if not event:
                    continue
                    
                if event.type == EventType.BAR:
                    # Update Portfolio Equity
                    price = event.data['close']
                    self.portfolio.update_equity({event.data['symbol']: price})
                    logger.info(f"Equity: {self.portfolio.equity:.2f} | PnL: {self.portfolio.pnl:.2f}")
                    
                    # 2. Strategy Analysis
                    self.strategy.on_bar(event)
                    
                    # Process generated orders
                    # (In a real event bus, strategy would put orders in queue)
                    # Here we catch the strategy output if it returns anything, 
                    # but Strategy.on_bar usually returns None and puts to engine queue.
                    # We need to wire strategy to engine queue.
                    pass 
                    
                # TODO: Wiring strategy output to execution
                # This requires the Strategy to have a reference to the Engine or return events.
                
            except Exception as e:
                logger.error(f"Engine Loop Error: {e}")
                time.sleep(1)
                
    def stop(self, signum=None, frame=None):
        logger.info("Stopping Engine...")
        self.active = False
        self.feed.stop()
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        config = sys.argv[1]
    else:
        config = "config/paper_trading.json"
        
    engine = LiveEngine(config)
    engine.run()
