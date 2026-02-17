"""
Exchange Manager — Unified adapter over ccxt for all exchanges.

FUSION_PLAN reference: Section 2.1.1, Fase 1.1
Source patterns: freqtrade exchange.py (4,123 LOC) + ccxt unified API

Features:
- Async-first design (all methods are coroutines)
- Rate limiting with token-bucket algorithm
- Retry with exponential backoff
- Pre-order validation (amount min, price limits, lot rounding)
- All prices returned as Decimal (never float for monetary values)
- Dry-run mode: simulates orders without sending to exchange
- SBE encoding hook for Rust engine communication

Dependencies: ccxt >= 4.0
"""

import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple

import ccxt.async_support as ccxt_async
import pandas as pd
from loguru import logger

from .config import ExchangeConfig


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Ticker:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal
    timestamp: int  # Unix nanoseconds UTC

    @property
    def spread(self) -> Decimal:
        if self.ask and self.bid:
            return self.ask - self.bid
        return Decimal("0")

    @property
    def spread_pct(self) -> Decimal:
        if self.last and self.last > 0:
            return self.spread / self.last
        return Decimal("0")


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str  # 'buy' | 'sell'
    order_type: str  # 'limit' | 'market'
    price: Decimal
    amount: Decimal
    filled: Decimal
    remaining: Decimal
    cost: Decimal
    fee: Decimal
    status: str  # 'open' | 'closed' | 'canceled'
    timestamp: int  # Unix nanoseconds UTC
    is_dry_run: bool = False


@dataclass
class OrderBook:
    bids: List[Tuple[Decimal, Decimal]]  # [(price, amount), ...]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp: int  # Unix nanoseconds UTC


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Token-bucket rate limiter.

    Refills tokens at a constant rate. Each request consumes one token.
    If no tokens available, caller awaits until refill.
    """

    def __init__(self, max_per_minute: int):
        self._max_tokens = max_per_minute
        self._tokens = float(max_per_minute)
        self._refill_rate = max_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now

            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._refill_rate
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


# =============================================================================
# Exceptions
# =============================================================================

class GoliathExchangeError(Exception):
    """Base exception for exchange-related errors."""


class GoliathInsufficientFunds(GoliathExchangeError):
    """Raised when balance is insufficient for an order."""


class GoliathInvalidOrder(GoliathExchangeError):
    """Raised when order parameters fail pre-validation."""


class GoliathAuthenticationError(GoliathExchangeError):
    """Raised when API credentials are invalid."""


# =============================================================================
# Helpers
# =============================================================================

def _to_decimal(value) -> Decimal:
    """Safely convert any numeric value to Decimal."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _ts_to_nanos(ms_timestamp) -> int:
    """Convert millisecond timestamp (ccxt standard) to nanosecond int64."""
    if ms_timestamp is None:
        return int(time.time() * 1_000_000_000)
    return int(ms_timestamp) * 1_000_000


# =============================================================================
# Exchange Manager
# =============================================================================

class ExchangeManager:
    """Unified exchange adapter over ccxt.

    All public methods are async coroutines.
    All prices/amounts are returned as Decimal.
    Timestamps are int64 Unix nanoseconds UTC.
    """

    def __init__(self, config: ExchangeConfig):
        self._config = config
        self._dry_run = config.sandbox
        self._rate_limiter = RateLimiter(config.rate_limit_per_min)

        exchange_class = getattr(ccxt_async, config.exchange_id, None)
        if exchange_class is None:
            raise GoliathExchangeError(f"Unknown exchange: {config.exchange_id}")

        self._exchange: ccxt_async.Exchange = exchange_class(config.to_ccxt_dict())
        self._markets_loaded = False
        self._dry_run_counter = 0

        logger.info(
            f"ExchangeManager initialized: exchange={config.exchange_id} "
            f"sandbox={config.sandbox} rate_limit={config.rate_limit_per_min}/min"
        )

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def _ensure_markets(self) -> None:
        """Load market metadata (symbols, limits, precision) if not yet loaded."""
        if not self._markets_loaded:
            await self._rate_limiter.acquire()
            await self._exchange.load_markets()
            self._markets_loaded = True
            logger.info(f"Markets loaded: {len(self._exchange.markets)} symbols available")

    async def close(self) -> None:
        """Gracefully close the exchange connection."""
        await self._exchange.close()
        logger.info("ExchangeManager closed")

    # -------------------------------------------------------------------------
    # Market Data
    # -------------------------------------------------------------------------

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Fetch current ticker for a symbol.

        Returns: Ticker with bid, ask, last, volume as Decimal.
        """
        await self._ensure_markets()
        await self._rate_limiter.acquire()

        raw = await self._retry(self._exchange.fetch_ticker, symbol)

        return Ticker(
            symbol=symbol,
            bid=_to_decimal(raw.get("bid")),
            ask=_to_decimal(raw.get("ask")),
            last=_to_decimal(raw.get("last")),
            volume=_to_decimal(raw.get("baseVolume")),
            timestamp=_ts_to_nanos(raw.get("timestamp")),
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """Fetch OHLCV candles.

        Args:
            symbol: Trading pair (e.g. 'BTC/USDT')
            timeframe: Candle period ('1m', '5m', '15m', '1h', '4h', '1d')
            since: Start time as Unix ms timestamp (None = exchange default)
            limit: Max candles to return (capped by exchange)

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
            - timestamp: int64 Unix nanoseconds UTC
            - open/high/low/close: Decimal
            - volume: Decimal
        """
        await self._ensure_markets()
        await self._rate_limiter.acquire()

        raw = await self._retry(
            self._exchange.fetch_ohlcv, symbol, timeframe, since, limit
        )

        if not raw:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        rows = []
        for candle in raw:
            rows.append({
                "timestamp": _ts_to_nanos(candle[0]),
                "open": _to_decimal(candle[1]),
                "high": _to_decimal(candle[2]),
                "low": _to_decimal(candle[3]),
                "close": _to_decimal(candle[4]),
                "volume": _to_decimal(candle[5]),
            })

        df = pd.DataFrame(rows)
        # Drop duplicate timestamps (dedup)
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    async def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Fetch order book with configurable depth.

        Returns: OrderBook with bids and asks as List[(Decimal, Decimal)].
        """
        await self._ensure_markets()
        await self._rate_limiter.acquire()

        raw = await self._retry(self._exchange.fetch_order_book, symbol, depth)

        bids = [(_to_decimal(p), _to_decimal(a)) for p, a in raw.get("bids", [])]
        asks = [(_to_decimal(p), _to_decimal(a)) for p, a in raw.get("asks", [])]

        return OrderBook(
            bids=bids,
            asks=asks,
            timestamp=_ts_to_nanos(raw.get("timestamp")),
        )

    # -------------------------------------------------------------------------
    # Account
    # -------------------------------------------------------------------------

    async def get_balance(self) -> Dict[str, Decimal]:
        """Fetch free balance for all assets.

        Returns: {'BTC': Decimal('0.5'), 'USDT': Decimal('1000.0'), ...}
        Only assets with balance > 0 are included.
        """
        await self._ensure_markets()
        await self._rate_limiter.acquire()

        raw = await self._retry(self._exchange.fetch_balance)

        balances = {}
        free = raw.get("free", {})
        for asset, amount in free.items():
            dec_amount = _to_decimal(amount)
            if dec_amount > 0:
                balances[asset] = dec_amount

        return balances

    async def get_fee(self, symbol: str, side: str = "buy") -> Decimal:
        """Fetch trading fee for a symbol.

        Returns: Fee as Decimal percentage (e.g. Decimal('0.001') = 0.1%).
        """
        await self._ensure_markets()

        market = self._exchange.market(symbol)
        if side == "buy":
            return _to_decimal(market.get("taker", 0.001))
        return _to_decimal(market.get("maker", 0.001))

    # -------------------------------------------------------------------------
    # Orders
    # -------------------------------------------------------------------------

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
        params: Optional[dict] = None,
    ) -> OrderResult:
        """Create an order with pre-validation.

        Validates (from freqtrade pattern):
        - amount >= market min amount
        - price within market price limits
        - cost (amount * price) >= market min cost
        - amount rounded to market precision

        If dry_run is True: returns a simulated OrderResult without sending.

        Raises:
            GoliathInvalidOrder: validation failed
            GoliathInsufficientFunds: not enough balance
            GoliathExchangeError: exchange rejected the order
        """
        await self._ensure_markets()

        market = self._exchange.market(symbol)
        validated_amount = self._validate_and_round_order(
            market, side, order_type, amount, price
        )

        if self._dry_run:
            return self._simulate_order(symbol, order_type, side, validated_amount, price)

        await self._rate_limiter.acquire()

        try:
            price_float = float(price) if price is not None else None
            raw = await self._retry(
                self._exchange.create_order,
                symbol,
                order_type,
                side,
                float(validated_amount),
                price_float,
                params or {},
            )
        except ccxt_async.InsufficientFunds as e:
            raise GoliathInsufficientFunds(str(e)) from e
        except ccxt_async.InvalidOrder as e:
            raise GoliathInvalidOrder(str(e)) from e
        except ccxt_async.AuthenticationError as e:
            raise GoliathAuthenticationError(str(e)) from e

        return OrderResult(
            order_id=str(raw.get("id", "")),
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=_to_decimal(raw.get("price")),
            amount=_to_decimal(raw.get("amount")),
            filled=_to_decimal(raw.get("filled")),
            remaining=_to_decimal(raw.get("remaining")),
            cost=_to_decimal(raw.get("cost")),
            fee=_to_decimal(raw.get("fee", {}).get("cost", 0)),
            status=raw.get("status", "unknown"),
            timestamp=_ts_to_nanos(raw.get("timestamp")),
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order. Returns True if successful."""
        await self._ensure_markets()
        await self._rate_limiter.acquire()

        try:
            await self._retry(self._exchange.cancel_order, order_id, symbol)
            logger.info(f"Order cancelled: {order_id} on {symbol}")
            return True
        except ccxt_async.OrderNotFound:
            logger.warning(f"Order not found for cancel: {order_id}")
            return False

    async def fetch_order(self, order_id: str, symbol: str) -> OrderResult:
        """Fetch status of a specific order."""
        await self._ensure_markets()
        await self._rate_limiter.acquire()

        raw = await self._retry(self._exchange.fetch_order, order_id, symbol)

        return OrderResult(
            order_id=str(raw.get("id", "")),
            symbol=symbol,
            side=raw.get("side", ""),
            order_type=raw.get("type", ""),
            price=_to_decimal(raw.get("price")),
            amount=_to_decimal(raw.get("amount")),
            filled=_to_decimal(raw.get("filled")),
            remaining=_to_decimal(raw.get("remaining")),
            cost=_to_decimal(raw.get("cost")),
            fee=_to_decimal(raw.get("fee", {}).get("cost", 0)),
            status=raw.get("status", "unknown"),
            timestamp=_ts_to_nanos(raw.get("timestamp")),
        )

    # -------------------------------------------------------------------------
    # Internal: Validation
    # -------------------------------------------------------------------------

    def _validate_and_round_order(
        self,
        market: dict,
        side: str,
        order_type: str,
        amount: Decimal,
        price: Optional[Decimal],
    ) -> Decimal:
        """Pre-order validation inspired by freqtrade exchange.py.

        Checks:
        1. amount >= limits.amount.min
        2. price in [limits.price.min, limits.price.max]
        3. cost = amount * price >= limits.cost.min
        4. amount rounded to precision.amount

        Returns: validated and rounded amount.
        Raises: GoliathInvalidOrder on failure.
        """
        limits = market.get("limits", {})
        precision = market.get("precision", {})

        # Round amount to exchange precision
        amount_precision = precision.get("amount")
        if amount_precision is not None:
            step = Decimal(str(10 ** -amount_precision))
            amount = amount.quantize(step, rounding=ROUND_DOWN)

        # Check minimum amount
        min_amount = limits.get("amount", {}).get("min")
        if min_amount is not None and amount < Decimal(str(min_amount)):
            raise GoliathInvalidOrder(
                f"Amount {amount} below minimum {min_amount} for {market['symbol']}"
            )

        # Check price limits (for limit orders)
        if price is not None and order_type == "limit":
            price_limits = limits.get("price", {})
            min_price = price_limits.get("min")
            max_price = price_limits.get("max")
            if min_price is not None and price < Decimal(str(min_price)):
                raise GoliathInvalidOrder(
                    f"Price {price} below minimum {min_price} for {market['symbol']}"
                )
            if max_price is not None and price > Decimal(str(max_price)):
                raise GoliathInvalidOrder(
                    f"Price {price} above maximum {max_price} for {market['symbol']}"
                )

        # Check minimum cost
        if price is not None:
            cost = amount * price
            min_cost = limits.get("cost", {}).get("min")
            if min_cost is not None and cost < Decimal(str(min_cost)):
                raise GoliathInvalidOrder(
                    f"Cost {cost} below minimum {min_cost} for {market['symbol']}"
                )

        return amount

    # -------------------------------------------------------------------------
    # Internal: Dry-run simulation
    # -------------------------------------------------------------------------

    def _simulate_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal],
    ) -> OrderResult:
        """Simulate order execution for dry-run mode."""
        self._dry_run_counter += 1
        simulated_id = f"DRY-{self._dry_run_counter:06d}"
        sim_price = price if price is not None else Decimal("0")

        logger.info(
            f"[DRY-RUN] Order {simulated_id}: {side.upper()} {amount} {symbol} "
            f"@ {sim_price} ({order_type})"
        )

        return OrderResult(
            order_id=simulated_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=sim_price,
            amount=amount,
            filled=amount,  # Simulated: instant fill
            remaining=Decimal("0"),
            cost=amount * sim_price,
            fee=Decimal("0"),
            status="closed",
            timestamp=int(time.time() * 1_000_000_000),
            is_dry_run=True,
        )

    # -------------------------------------------------------------------------
    # Internal: Retry with exponential backoff
    # -------------------------------------------------------------------------

    async def _retry(self, fn, *args, **kwargs):
        """Call fn with retry and exponential backoff.

        Retries on NetworkError only. Other errors propagate immediately.
        """
        last_error = None
        delay = self._config.retry_delay_base

        for attempt in range(1, self._config.retry_count + 1):
            try:
                return await fn(*args, **kwargs)
            except ccxt_async.NetworkError as e:
                last_error = e
                logger.warning(
                    f"Network error (attempt {attempt}/{self._config.retry_count}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            except ccxt_async.ExchangeError:
                raise

        raise GoliathExchangeError(
            f"Failed after {self._config.retry_count} retries: {last_error}"
        )
