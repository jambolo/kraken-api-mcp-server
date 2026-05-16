from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from ..config import Config
from ..http_client import KrakenHttpClient


class _Cache:
    def __init__(self, ttl_s: float) -> None:
        self.ttl = ttl_s
        self._value: Any = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        return self._value is not None and (time.monotonic() - self._fetched_at) < self.ttl

    async def get(self, fetch_fn) -> Any:
        async with self._lock:
            if not self.is_fresh():
                result = await fetch_fn()
                self._value = result
                self._fetched_at = time.monotonic()
            return self._value


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:
    _instruments_cache = _Cache(300.0)
    _trading_cache = _Cache(300.0)
    _status_cache = _Cache(30.0)
    _tickers_cache = _Cache(5.0)

    @mcp.resource("kraken-futures://instruments")
    async def futures_instruments() -> str:
        """All Kraken Futures instruments with full contract specifications. Cached for 5 minutes.

        Each instrument includes: contract size, tick size, maximum leverage, trading hours,
        margin tier schedule, funding parameters (for perpetuals), expiry date (for dated futures),
        underlying index, and current trading status.
        Read this before placing orders to verify lot sizes and price precision.
        """
        data = await _instruments_cache.get(
            lambda: client.futures_public_get("/derivatives/api/v3/instruments")
        )
        return json.dumps(data)

    @mcp.resource("kraken-futures://instruments/trading")
    async def futures_instruments_trading() -> str:
        """Kraken Futures instruments currently available for trading (status='trading'). Cached for 5 minutes.

        A filtered subset of kraken-futures://instruments. Use this when building
        order forms or listing tradable markets to exclude suspended instruments.
        """
        data = await _trading_cache.get(
            lambda: client.futures_public_get("/derivatives/api/v3/instruments/trading")
        )
        return json.dumps(data)

    @mcp.resource("kraken-futures://instrument-status")
    async def futures_instrument_status() -> str:
        """Trading status for all Kraken Futures instruments. Cached for 30 seconds.

        Status values: 'trading', 'suspended', 'cancel_only', 'post_only'.
        Check this before placing orders to catch mid-session status changes.
        More granular than kraken-futures://instruments/trading.
        """
        data = await _status_cache.get(
            lambda: client.futures_public_get("/derivatives/api/v3/instruments/status")
        )
        return json.dumps(data)

    @mcp.resource("kraken-futures://tickers")
    async def futures_tickers() -> str:
        """Live ticker data for all Kraken Futures symbols. Cached for 5 seconds.

        Each ticker includes last price, bid/ask with sizes, 24-hour volume and change,
        open interest, mark price, funding rate (perpetuals), and index price.
        For a single symbol, call the futures_public_ticker tool directly.
        """
        data = await _tickers_cache.get(
            lambda: client.futures_public_get("/derivatives/api/v3/tickers")
        )
        return json.dumps(data)
