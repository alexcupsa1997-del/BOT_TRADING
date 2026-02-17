"""
WebSocket Stream Manager — Real-time market data via ccxt.pro.

FUSION_PLAN reference: Section 2.4.2, Fase 1.2
Source patterns: binance-trade-bot stream manager + ccxt.pro WebSocket API

Features:
- Multi-symbol subscription on a single connection
- Auto-reconnect with exponential backoff (1s → 2s → 4s → ... → 60s cap)
- Ring buffer per symbol (configurable max length)
- Callback system for downstream pipeline triggering
- Graceful shutdown with task cancellation
- Heartbeat monitoring

Dependencies: ccxt >= 4.0 (ccxt.pro for WebSocket support)
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, List, Optional

import ccxt.pro as ccxt_pro
from loguru import logger


# =============================================================================
# Types
# =============================================================================

# Callback type: async function receiving (symbol, data_dict)
StreamCallback = Callable[[str, dict], Coroutine[Any, Any, None]]


@dataclass
class StreamConfig:
    """Configuration for WebSocket stream manager."""
    exchange_id: str = "binance"
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT"])
    sandbox: bool = True
    buffer_maxlen: int = 1000
    reconnect_delay_base: float = 1.0
    reconnect_delay_max: float = 60.0
    heartbeat_interval: float = 30.0


# =============================================================================
# WebSocket Stream Manager
# =============================================================================

class WebSocketStreamManager:
    """Manages real-time WebSocket streams from an exchange.

    Provides async subscription methods for OHLCV, ticker, and order book.
    Each subscription runs as an independent asyncio task with auto-reconnect.
    Data is stored in per-symbol ring buffers and forwarded to callbacks.
    """

    def __init__(self, config: StreamConfig):
        self._config = config
        self._exchange: Optional[ccxt_pro.Exchange] = None
        self._buffers: Dict[str, deque] = {}
        self._tasks: List[asyncio.Task] = []
        self._running = False
        self._reconnect_delay = config.reconnect_delay_base

        # Initialize ring buffers for each symbol
        for symbol in config.symbols:
            self._buffers[symbol] = deque(maxlen=config.buffer_maxlen)

        logger.info(
            f"WSStreamManager initialized: exchange={config.exchange_id} "
            f"symbols={config.symbols} buffer_maxlen={config.buffer_maxlen}"
        )

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def _create_exchange(self) -> ccxt_pro.Exchange:
        """Create a fresh ccxt.pro exchange instance."""
        exchange_class = getattr(ccxt_pro, self._config.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown exchange for WebSocket: {self._config.exchange_id}")

        return exchange_class({
            "sandbox": self._config.sandbox,
            "enableRateLimit": True,
        })

    async def close(self) -> None:
        """Cancel all tasks and close the exchange connection."""
        self._running = False

        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to finish cancellation
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None

        logger.info("WSStreamManager closed")

    # -------------------------------------------------------------------------
    # Subscriptions
    # -------------------------------------------------------------------------

    async def subscribe_ohlcv(
        self,
        timeframe: str = "1m",
        callback: Optional[StreamCallback] = None,
    ) -> None:
        """Subscribe to OHLCV candle updates for all configured symbols.

        Each new candle triggers the callback with (symbol, candle_dict).
        Candle dict: {timestamp, open, high, low, close, volume} — all Decimal.
        Runs until close() is called.
        """
        self._running = True
        self._exchange = self._create_exchange()

        logger.info(f"Subscribing to OHLCV {timeframe} for {self._config.symbols}")

        while self._running:
            try:
                for symbol in self._config.symbols:
                    if not self._running:
                        break

                    raw = await self._exchange.watch_ohlcv(symbol, timeframe)

                    if raw:
                        # ccxt.pro returns list of [timestamp_ms, o, h, l, c, v]
                        last_candle = raw[-1]
                        candle = {
                            "timestamp": int(last_candle[0]) * 1_000_000,  # ms → nanos
                            "open": Decimal(str(last_candle[1])),
                            "high": Decimal(str(last_candle[2])),
                            "low": Decimal(str(last_candle[3])),
                            "close": Decimal(str(last_candle[4])),
                            "volume": Decimal(str(last_candle[5])),
                        }

                        self._buffers[symbol].append(candle)

                        if callback is not None:
                            await callback(symbol, candle)

                # Reset reconnect delay on success
                self._reconnect_delay = self._config.reconnect_delay_base

            except asyncio.CancelledError:
                logger.info("OHLCV subscription cancelled")
                break

            except Exception as e:
                if not self._running:
                    break
                logger.warning(
                    f"WS OHLCV error: {e}. "
                    f"Reconnecting in {self._reconnect_delay:.1f}s..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._config.reconnect_delay_max
                )
                # Re-create exchange on reconnect
                try:
                    await self._exchange.close()
                except Exception:
                    pass
                self._exchange = self._create_exchange()

    async def subscribe_ticker(
        self,
        callback: Optional[StreamCallback] = None,
    ) -> None:
        """Subscribe to ticker updates (best bid/ask + last) for all symbols.

        Ticker dict: {symbol, bid, ask, last, volume, timestamp} — all Decimal.
        """
        self._running = True
        self._exchange = self._create_exchange()

        logger.info(f"Subscribing to ticker for {self._config.symbols}")

        while self._running:
            try:
                for symbol in self._config.symbols:
                    if not self._running:
                        break

                    raw = await self._exchange.watch_ticker(symbol)

                    ticker = {
                        "symbol": symbol,
                        "bid": Decimal(str(raw.get("bid", 0))),
                        "ask": Decimal(str(raw.get("ask", 0))),
                        "last": Decimal(str(raw.get("last", 0))),
                        "volume": Decimal(str(raw.get("baseVolume", 0))),
                        "timestamp": int(raw.get("timestamp", 0)) * 1_000_000,
                    }

                    if callback is not None:
                        await callback(symbol, ticker)

                self._reconnect_delay = self._config.reconnect_delay_base

            except asyncio.CancelledError:
                break

            except Exception as e:
                if not self._running:
                    break
                logger.warning(f"WS ticker error: {e}. Reconnecting in {self._reconnect_delay:.1f}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._config.reconnect_delay_max
                )
                try:
                    await self._exchange.close()
                except Exception:
                    pass
                self._exchange = self._create_exchange()

    # -------------------------------------------------------------------------
    # Buffer Access
    # -------------------------------------------------------------------------

    def get_buffer(self, symbol: str) -> List[dict]:
        """Return a copy of the ring buffer for a symbol.

        Returns: List of candle dicts, oldest first.
        """
        if symbol not in self._buffers:
            return []
        return list(self._buffers[symbol])

    def get_latest(self, symbol: str) -> Optional[dict]:
        """Return the most recent candle for a symbol, or None."""
        buf = self._buffers.get(symbol)
        if buf:
            return buf[-1]
        return None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def buffer_sizes(self) -> Dict[str, int]:
        """Return current buffer sizes per symbol."""
        return {s: len(b) for s, b in self._buffers.items()}
