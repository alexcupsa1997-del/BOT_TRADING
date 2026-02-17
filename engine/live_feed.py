"""
engine/live_feed.py
===================

Real-time Data Feed using CCXT.
Polls exchange API for OHLCV data and yields BAR events.
"""

import time
import ccxt
from decimal import Decimal
from typing import Optional, List
from loguru import logger
from datetime import datetime, timezone

from engine.events import Event, EventType
from engine.data import DataFeed

class RealTimeDataFeed(DataFeed):
    """
    Polls an exchange for real-time OHLCV data.
    Designed for Paper Trading and Live Trading.
    """
    
    def __init__(self, exchange_id: str = 'binance', symbol: str = 'BTC/USDT', timeframe: str = '1m', limit: int = 5):
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.limit = limit
        
        # Rate Limit handling
        self.exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True,
        })
        
        self.last_timestamp = 0
        self._running = True
        
    def load(self, start_date: str = None, end_date: str = None) -> None:
        """
        For Live Feed, 'load' might fetch recent history to warm up indicators.
        """
        logger.info(f"Connecting to {self.exchange_id} for {self.symbol}...")
        try:
            self.exchange.load_markets()
            logger.info("Markets loaded.")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    def reset(self) -> None:
        self.last_timestamp = 0

    def get_next(self) -> Optional[Event]:
        """
        Blocking call that waits for a new candle.
        In a real async engine, this would be non-blocking or callback-based.
        Here we poll loops.
        """
        while self._running:
            try:
                # Fetch recent OHLCV
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=self.limit)
                if not ohlcv:
                    time.sleep(1)
                    continue
                
                # Get the latest CLOSED candle
                # Usually the last one is still open. We want the one before it.
                # Or if we want real-time updates, we take the last one but mark it incomplete?
                # For this simple bot, we wait for candle close.
                
                # Check timestamps
                # ohlcv structure: [timestamp, open, high, low, close, volume]
                # timestamp is ms
                
                # We usually get the completed candle at index -2 if index -1 is current open candle.
                # Binances returns the current OPEN candle as the last element.
                
                current_candle = ohlcv[-1]
                completed_candle = ohlcv[-2]
                
                ts = completed_candle[0]
                
                if ts > self.last_timestamp:
                    self.last_timestamp = ts
                    
                    data = {
                        "symbol": self.symbol.replace("/", ""), # Normalize to internal format
                        "timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                        "open": Decimal(str(completed_candle[1])),
                        "high": Decimal(str(completed_candle[2])),
                        "low": Decimal(str(completed_candle[3])),
                        "close": Decimal(str(completed_candle[4])),
                        "volume": Decimal(str(completed_candle[5])),
                    }
                    
                    logger.info(f"New Bar: {data['timestamp']} {data['close']}")
                    return Event(type=EventType.BAR, data=data)
                
                # Wait before polling again
                # Sleep depending on timeframe? For 1m, polling every 5s is fine.
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error fetching data: {e}")
                time.sleep(10) # Backoff
                
        return None

    def stop(self):
        self._running = False
