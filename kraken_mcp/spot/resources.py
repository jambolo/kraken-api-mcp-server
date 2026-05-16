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
    _system_status_cache = _Cache(60.0)
    _assets_cache = _Cache(3600.0)
    _pairs_cache = _Cache(3600.0)

    @mcp.resource("kraken-spot://system-status")
    async def spot_system_status() -> str:
        """Current Kraken Spot system status and trading mode. Cached for 60 seconds.

        Returns JSON with fields:
        - status: 'online' | 'cancel_only' | 'post_only' | 'limit_only' | 'maintenance'
        - timestamp: RFC 1123 server time

        Check this before placing orders — anything other than 'online' restricts trading.
        """
        data = await _system_status_cache.get(
            lambda: client.spot_public_get("/0/public/SystemStatus")
        )
        return json.dumps(data)

    @mcp.resource("kraken-spot://assets")
    async def spot_assets() -> str:
        """All assets available on Kraken Spot with their specifications. Cached for 1 hour.

        Each asset entry includes: altname (display name), aclass, decimals (on-chain),
        display_decimals (UI precision), status, and deposit/withdrawal availability.
        Use altnames when referencing assets in tool parameters.
        """
        data = await _assets_cache.get(
            lambda: client.spot_public_get("/0/public/Assets")
        )
        return json.dumps(data)

    @mcp.resource("kraken-spot://asset-pairs")
    async def spot_asset_pairs() -> str:
        """All tradable asset pairs on Kraken Spot with full specifications. Cached for 1 hour.

        Each pair entry includes: altname, base/quote assets, lot/price decimals,
        min/max order size, fee schedules (maker/taker), margin parameters,
        leverage levels, and trading status. Prefer this resource over the
        spot_public_asset_pairs tool for repeated lookups.
        """
        data = await _pairs_cache.get(
            lambda: client.spot_public_get("/0/public/AssetPairs")
        )
        return json.dumps(data)

    @mcp.resource("kraken-spot://asset-pairs/{pair}")
    async def spot_asset_pair(pair: str) -> str:
        """Specification for a single Spot asset pair, filtered from the cached pairs list.

        Returns the same fields as kraken-spot://asset-pairs but for one pair only.
        Accepts either the pair's internal name (e.g. 'XXBTZUSD') or its altname (e.g. 'XBTUSD').
        Returns {ok: true, data: null} if the pair is not found.
        """
        data = await _pairs_cache.get(
            lambda: client.spot_public_get("/0/public/AssetPairs")
        )
        result = data.get("data") or {}
        match = result.get(pair) or result.get(pair.upper())
        if match is None:
            for v in result.values():
                if isinstance(v, dict) and v.get("altname", "").upper() == pair.upper():
                    match = v
                    break
        return json.dumps({"ok": True, "data": match, "errors": []})

    @mcp.resource("kraken-spot://ticker/{pair}")
    async def spot_ticker(pair: str) -> str:
        """Live ticker for a single Spot asset pair. Fetched on every read (no cache).

        Returns full ticker data: best bid/ask with lot volumes, last trade price and lot volume,
        today's open/high/low/close, 24-hour volume and VWAP, number of trades,
        and rolling 24-hour equivalents. Prices are strings.
        """
        data = await client.spot_public_get("/0/public/Ticker", {"pair": pair})
        return json.dumps(data)

    @mcp.resource("kraken-safety://config")
    async def safety_config() -> str:
        """Current gate configuration showing which features are enabled for this server instance.

        Returns JSON with fields:
        - trading_enabled: whether order placement/edit/cancel tools are active
        - transfers_enabled: whether internal transfer tools are active
        - futures_env: 'live' or 'demo'
        - has_spot_auth: whether Spot API credentials are configured
        - has_futures_auth: whether Futures API credentials are configured
        - spot_rate_limit_tier: 'starter' | 'intermediate' | 'pro'

        Read this resource before attempting trading or transfer operations.
        """
        return json.dumps({
            "trading_enabled": cfg.trading_enabled,
            "transfers_enabled": cfg.transfers_enabled,
            "futures_env": cfg.futures_env,
            "has_spot_auth": cfg.has_spot_auth,
            "has_futures_auth": cfg.has_futures_auth,
            "spot_rate_limit_tier": cfg.spot_rate_limit_tier,
        })
