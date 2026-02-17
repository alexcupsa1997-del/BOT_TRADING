"""
Tests for ExchangeManager (FASE 1.1).

Tests use mocked ccxt exchange — no real network calls.
Validates: Decimal output, rate limiting, validation, dry-run, retry logic.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import ExchangeConfig
from src.integration.exchange_manager import (
    ExchangeManager,
    GoliathExchangeError,
    GoliathInsufficientFunds,
    GoliathInvalidOrder,
    OrderBook,
    OrderResult,
    RateLimiter,
    Ticker,
    _to_decimal,
    _ts_to_nanos,
)


# =============================================================================
# Helper: _to_decimal and _ts_to_nanos
# =============================================================================


class TestHelpers:
    def test_to_decimal_from_float(self):
        result = _to_decimal(1.5)
        assert isinstance(result, Decimal)
        assert result == Decimal("1.5")

    def test_to_decimal_from_none(self):
        assert _to_decimal(None) == Decimal("0")

    def test_to_decimal_from_decimal(self):
        d = Decimal("99.99")
        assert _to_decimal(d) is d

    def test_to_decimal_from_int(self):
        assert _to_decimal(42) == Decimal("42")

    def test_to_decimal_from_string_numeric(self):
        assert _to_decimal("123.456") == Decimal("123.456")

    def test_ts_to_nanos_converts_ms(self):
        assert _ts_to_nanos(1000) == 1_000_000_000

    def test_ts_to_nanos_none_returns_current(self):
        result = _ts_to_nanos(None)
        assert result > 0
        assert isinstance(result, int)


# =============================================================================
# RateLimiter
# =============================================================================


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        rl = RateLimiter(max_per_minute=60)
        # Should not block for a few calls
        for _ in range(3):
            await rl.acquire()

    @pytest.mark.asyncio
    async def test_acquire_tracks_tokens(self):
        rl = RateLimiter(max_per_minute=2)
        await rl.acquire()
        await rl.acquire()
        # Third call should wait — but we don't assert timing here,
        # just that it completes without error.


# =============================================================================
# Ticker dataclass
# =============================================================================


class TestTicker:
    def test_spread(self):
        t = Ticker(
            symbol="BTC/USDT",
            bid=Decimal("50000"),
            ask=Decimal("50010"),
            last=Decimal("50005"),
            volume=Decimal("100"),
            timestamp=0,
        )
        assert t.spread == Decimal("10")

    def test_spread_pct(self):
        t = Ticker(
            symbol="BTC/USDT",
            bid=Decimal("50000"),
            ask=Decimal("50050"),
            last=Decimal("50000"),
            volume=Decimal("100"),
            timestamp=0,
        )
        assert t.spread_pct == Decimal("50") / Decimal("50000")

    def test_spread_zero_last(self):
        t = Ticker(
            symbol="X", bid=Decimal("0"), ask=Decimal("0"),
            last=Decimal("0"), volume=Decimal("0"), timestamp=0,
        )
        assert t.spread_pct == Decimal("0")


# =============================================================================
# ExchangeManager — mocked
# =============================================================================


def _make_manager(exchange_id="binance", sandbox=True) -> ExchangeManager:
    """Create ExchangeManager with a mocked ccxt exchange."""
    config = ExchangeConfig(exchange_id=exchange_id, sandbox=sandbox)
    em = ExchangeManager(config)
    # Replace real exchange with mock
    mock_exchange = AsyncMock()
    mock_exchange.load_markets = AsyncMock(return_value={})
    mock_exchange.markets = {
        "BTC/USDT": {
            "symbol": "BTC/USDT",
            "limits": {
                "amount": {"min": 0.00001},
                "price": {"min": 0.01, "max": 1000000},
                "cost": {"min": 10},
            },
            "precision": {"amount": 5, "price": 2},
            "taker": 0.001,
            "maker": 0.001,
        }
    }
    mock_exchange.market = MagicMock(
        side_effect=lambda s: mock_exchange.markets.get(s, {})
    )
    mock_exchange.close = AsyncMock()
    em._exchange = mock_exchange
    em._markets_loaded = True
    return em


class TestExchangeManagerFetchTicker:
    @pytest.mark.asyncio
    async def test_returns_ticker_with_decimals(self):
        em = _make_manager()
        em._exchange.fetch_ticker = AsyncMock(return_value={
            "bid": 50000.0,
            "ask": 50001.0,
            "last": 50000.5,
            "baseVolume": 1234.5,
            "timestamp": 1700000000000,
        })

        ticker = await em.fetch_ticker("BTC/USDT")

        assert isinstance(ticker, Ticker)
        assert isinstance(ticker.bid, Decimal)
        assert isinstance(ticker.ask, Decimal)
        assert isinstance(ticker.last, Decimal)
        assert ticker.bid == Decimal("50000.0")
        assert ticker.ask == Decimal("50001.0")
        assert isinstance(ticker.timestamp, int)
        await em.close()


class TestExchangeManagerFetchOHLCV:
    @pytest.mark.asyncio
    async def test_returns_dataframe_with_decimals(self):
        em = _make_manager()
        em._exchange.fetch_ohlcv = AsyncMock(return_value=[
            [1700000000000, 50000, 50100, 49900, 50050, 100],
            [1700003600000, 50050, 50200, 50000, 50150, 110],
        ])

        df = await em.fetch_ohlcv("BTC/USDT", "1h", limit=2)

        assert len(df) == 2
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert isinstance(df.iloc[0]["close"], Decimal)
        assert df.iloc[0]["close"] == Decimal("50050")
        # pandas stores int64 as np.int64, which is a subclass of np.integer
        import numpy as np
        assert np.issubdtype(type(df.iloc[0]["timestamp"]), np.integer)
        await em.close()

    @pytest.mark.asyncio
    async def test_deduplicates_timestamps(self):
        em = _make_manager()
        em._exchange.fetch_ohlcv = AsyncMock(return_value=[
            [1700000000000, 100, 101, 99, 100, 10],
            [1700000000000, 100, 101, 99, 100.5, 11],  # Duplicate ts
            [1700003600000, 101, 102, 100, 101, 12],
        ])

        df = await em.fetch_ohlcv("BTC/USDT", "1h")

        assert len(df) == 2  # Deduped
        # Keep last occurrence
        assert df.iloc[0]["close"] == Decimal("100.5")
        await em.close()

    @pytest.mark.asyncio
    async def test_empty_response(self):
        em = _make_manager()
        em._exchange.fetch_ohlcv = AsyncMock(return_value=[])

        df = await em.fetch_ohlcv("BTC/USDT", "1h")

        assert len(df) == 0
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        await em.close()


class TestExchangeManagerFetchOrderBook:
    @pytest.mark.asyncio
    async def test_returns_order_book_with_decimals(self):
        em = _make_manager()
        em._exchange.fetch_order_book = AsyncMock(return_value={
            "bids": [[50000, 1.5], [49999, 2.0]],
            "asks": [[50001, 1.0], [50002, 3.0]],
            "timestamp": 1700000000000,
        })

        ob = await em.fetch_order_book("BTC/USDT", depth=2)

        assert isinstance(ob, OrderBook)
        assert len(ob.bids) == 2
        assert len(ob.asks) == 2
        assert ob.bids[0] == (Decimal("50000"), Decimal("1.5"))
        assert ob.asks[0] == (Decimal("50001"), Decimal("1.0"))
        await em.close()


class TestExchangeManagerBalance:
    @pytest.mark.asyncio
    async def test_returns_nonzero_balances(self):
        em = _make_manager()
        em._exchange.fetch_balance = AsyncMock(return_value={
            "free": {"BTC": 0.5, "USDT": 1000.0, "ETH": 0.0},
        })

        balances = await em.get_balance()

        assert "BTC" in balances
        assert "USDT" in balances
        assert "ETH" not in balances  # Zero balance excluded
        assert isinstance(balances["BTC"], Decimal)
        assert balances["BTC"] == Decimal("0.5")
        await em.close()


class TestExchangeManagerFee:
    @pytest.mark.asyncio
    async def test_returns_decimal_fee(self):
        em = _make_manager()

        fee = await em.get_fee("BTC/USDT", "buy")

        assert isinstance(fee, Decimal)
        assert fee == Decimal("0.001")
        await em.close()


class TestExchangeManagerDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_order_returns_simulated(self):
        em = _make_manager(sandbox=True)

        result = await em.create_order(
            symbol="BTC/USDT",
            order_type="limit",
            side="buy",
            amount=Decimal("0.01"),
            price=Decimal("50000"),
        )

        assert isinstance(result, OrderResult)
        assert result.is_dry_run is True
        assert result.order_id.startswith("DRY-")
        assert result.status == "closed"
        assert result.filled == Decimal("0.01")
        assert isinstance(result.price, Decimal)
        await em.close()

    @pytest.mark.asyncio
    async def test_dry_run_increments_counter(self):
        em = _make_manager(sandbox=True)

        r1 = await em.create_order("BTC/USDT", "limit", "buy", Decimal("0.01"), Decimal("50000"))
        r2 = await em.create_order("BTC/USDT", "limit", "sell", Decimal("0.01"), Decimal("51000"))

        assert r1.order_id == "DRY-000001"
        assert r2.order_id == "DRY-000002"
        await em.close()


class TestExchangeManagerValidation:
    @pytest.mark.asyncio
    async def test_rejects_below_min_amount(self):
        em = _make_manager(sandbox=True)

        with pytest.raises(GoliathInvalidOrder, match="below minimum"):
            await em.create_order(
                "BTC/USDT", "limit", "buy",
                amount=Decimal("0.000001"),  # Below 0.00001 min
                price=Decimal("50000"),
            )
        await em.close()

    @pytest.mark.asyncio
    async def test_rejects_below_min_cost(self):
        em = _make_manager(sandbox=True)

        with pytest.raises(GoliathInvalidOrder, match="Cost .* below minimum"):
            await em.create_order(
                "BTC/USDT", "limit", "buy",
                amount=Decimal("0.00001"),  # cost = 0.00001 * 1 = 0.00001 < 10
                price=Decimal("1"),
            )
        await em.close()

    @pytest.mark.asyncio
    async def test_rejects_price_above_max(self):
        em = _make_manager(sandbox=True)

        with pytest.raises(GoliathInvalidOrder, match="above maximum"):
            await em.create_order(
                "BTC/USDT", "limit", "buy",
                amount=Decimal("0.01"),
                price=Decimal("2000000"),  # Above 1,000,000 max
            )
        await em.close()

    @pytest.mark.asyncio
    async def test_rounds_amount_to_precision(self):
        em = _make_manager(sandbox=True)

        result = await em.create_order(
            "BTC/USDT", "limit", "buy",
            amount=Decimal("0.123456789"),  # Precision=5 → rounds to 0.12345
            price=Decimal("50000"),
        )

        assert result.amount == Decimal("0.12345")
        await em.close()


class TestExchangeManagerRetry:
    @pytest.mark.asyncio
    async def test_retries_on_network_error(self):
        import ccxt.async_support as ccxt_async_mod

        em = _make_manager()
        call_count = 0

        async def flaky_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ccxt_async_mod.NetworkError("timeout")
            return {"bid": 50000, "ask": 50001, "last": 50000.5,
                    "baseVolume": 100, "timestamp": 1700000000000}

        em._exchange.fetch_ticker = flaky_fetch
        em._config.retry_delay_base = 0.01  # Fast retry for tests

        ticker = await em.fetch_ticker("BTC/USDT")

        assert call_count == 3
        assert ticker.last == Decimal("50000.5")
        await em.close()

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        import ccxt.async_support as ccxt_async_mod

        em = _make_manager()
        em._exchange.fetch_ticker = AsyncMock(
            side_effect=ccxt_async_mod.NetworkError("timeout")
        )
        em._config.retry_delay_base = 0.01
        em._config.retry_count = 2

        with pytest.raises(GoliathExchangeError, match="Failed after 2 retries"):
            await em.fetch_ticker("BTC/USDT")
        await em.close()
