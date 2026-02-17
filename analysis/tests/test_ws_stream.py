"""
Tests for WebSocketStreamManager (FASE 1.2).

Tests use mocked ccxt.pro exchange — no real WebSocket connections.
Validates: buffer management, callback invocation, reconnect logic, Decimal output.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integration.ws_stream import (
    StreamConfig,
    WebSocketStreamManager,
)


# =============================================================================
# StreamConfig
# =============================================================================


class TestStreamConfig:
    def test_defaults(self):
        config = StreamConfig()
        assert config.exchange_id == "binance"
        assert config.symbols == ["BTC/USDT"]
        assert config.buffer_maxlen == 1000
        assert config.reconnect_delay_max == 60.0

    def test_custom_symbols(self):
        config = StreamConfig(symbols=["ETH/USDT", "SOL/USDT"])
        assert len(config.symbols) == 2


# =============================================================================
# WebSocketStreamManager — Initialization
# =============================================================================


class TestWSManagerInit:
    def test_creates_buffers_for_each_symbol(self):
        config = StreamConfig(symbols=["BTC/USDT", "ETH/USDT"])
        ws = WebSocketStreamManager(config)

        assert "BTC/USDT" in ws._buffers
        assert "ETH/USDT" in ws._buffers
        assert ws.buffer_sizes == {"BTC/USDT": 0, "ETH/USDT": 0}

    def test_not_running_initially(self):
        ws = WebSocketStreamManager(StreamConfig())
        assert ws.is_running is False


# =============================================================================
# Buffer Operations
# =============================================================================


class TestWSManagerBuffers:
    def test_get_buffer_empty(self):
        ws = WebSocketStreamManager(StreamConfig(symbols=["BTC/USDT"]))
        assert ws.get_buffer("BTC/USDT") == []

    def test_get_buffer_unknown_symbol(self):
        ws = WebSocketStreamManager(StreamConfig(symbols=["BTC/USDT"]))
        assert ws.get_buffer("UNKNOWN/PAIR") == []

    def test_get_latest_none_when_empty(self):
        ws = WebSocketStreamManager(StreamConfig(symbols=["BTC/USDT"]))
        assert ws.get_latest("BTC/USDT") is None

    def test_buffer_stores_items(self):
        ws = WebSocketStreamManager(StreamConfig(symbols=["BTC/USDT"], buffer_maxlen=5))
        # Manually append to buffer (simulate what subscribe_ohlcv does)
        for i in range(3):
            ws._buffers["BTC/USDT"].append({"close": Decimal(str(50000 + i))})

        assert ws.buffer_sizes == {"BTC/USDT": 3}
        assert ws.get_latest("BTC/USDT")["close"] == Decimal("50002")

    def test_buffer_maxlen_respected(self):
        ws = WebSocketStreamManager(StreamConfig(symbols=["BTC/USDT"], buffer_maxlen=3))
        for i in range(10):
            ws._buffers["BTC/USDT"].append({"value": i})

        assert ws.buffer_sizes == {"BTC/USDT": 3}
        buf = ws.get_buffer("BTC/USDT")
        assert buf[0]["value"] == 7  # Oldest surviving
        assert buf[-1]["value"] == 9  # Newest

    def test_get_buffer_returns_copy(self):
        ws = WebSocketStreamManager(StreamConfig(symbols=["BTC/USDT"]))
        ws._buffers["BTC/USDT"].append({"v": 1})

        buf = ws.get_buffer("BTC/USDT")
        buf.clear()  # Modifying the copy

        assert ws.buffer_sizes == {"BTC/USDT": 1}  # Original unchanged


# =============================================================================
# Subscribe OHLCV — mocked
# =============================================================================


class TestWSManagerSubscribeOHLCV:
    @pytest.mark.asyncio
    async def test_callback_receives_decimal_candles(self):
        config = StreamConfig(symbols=["BTC/USDT"])
        ws = WebSocketStreamManager(config)

        received = []
        call_count = 0

        async def mock_watch_ohlcv(symbol, timeframe):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                # Stop after 2 iterations
                ws._running = False
                return []
            return [[1700000000000, 50000, 50100, 49900, 50050, 100.5]]

        mock_exchange = MagicMock()
        mock_exchange.watch_ohlcv = mock_watch_ohlcv
        mock_exchange.close = AsyncMock()

        # Patch _create_exchange to return our mock
        ws._create_exchange = lambda: mock_exchange

        async def on_candle(symbol, candle):
            received.append((symbol, candle))

        await ws.subscribe_ohlcv("1m", callback=on_candle)

        assert len(received) >= 1
        symbol, candle = received[0]
        assert symbol == "BTC/USDT"
        assert isinstance(candle["close"], Decimal)
        assert candle["close"] == Decimal("50050")
        assert isinstance(candle["volume"], Decimal)
        assert isinstance(candle["timestamp"], int)

    @pytest.mark.asyncio
    async def test_data_stored_in_buffer(self):
        config = StreamConfig(symbols=["BTC/USDT"])
        ws = WebSocketStreamManager(config)

        call_count = 0

        async def mock_watch_ohlcv(symbol, timeframe):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                ws._running = False
                return []
            return [[1700000000000 + call_count * 60000,
                     50000 + call_count, 50100, 49900, 50050 + call_count, 100]]

        mock_exchange = MagicMock()
        mock_exchange.watch_ohlcv = mock_watch_ohlcv
        mock_exchange.close = AsyncMock()
        ws._create_exchange = lambda: mock_exchange

        await ws.subscribe_ohlcv("1m")

        assert ws.buffer_sizes["BTC/USDT"] >= 1

    @pytest.mark.asyncio
    async def test_reconnect_on_error(self):
        config = StreamConfig(symbols=["BTC/USDT"], reconnect_delay_base=0.01)
        ws = WebSocketStreamManager(config)

        call_count = 0

        async def mock_watch_ohlcv(symbol, timeframe):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("simulated disconnect")
            if call_count == 2:
                return [[1700000000000, 50000, 50100, 49900, 50050, 100]]
            ws._running = False
            return []

        mock_exchange = MagicMock()
        mock_exchange.watch_ohlcv = mock_watch_ohlcv
        mock_exchange.close = AsyncMock()
        ws._create_exchange = lambda: mock_exchange

        await ws.subscribe_ohlcv("1m")

        # Should have survived the error and received data on retry
        assert call_count >= 2


# =============================================================================
# Close / Lifecycle
# =============================================================================


class TestWSManagerLifecycle:
    @pytest.mark.asyncio
    async def test_close_sets_not_running(self):
        ws = WebSocketStreamManager(StreamConfig())
        ws._running = True
        ws._exchange = MagicMock()
        ws._exchange.close = AsyncMock()

        await ws.close()

        assert ws.is_running is False

    @pytest.mark.asyncio
    async def test_close_without_exchange(self):
        ws = WebSocketStreamManager(StreamConfig())
        # Should not raise even if no exchange was created
        await ws.close()
        assert ws.is_running is False
