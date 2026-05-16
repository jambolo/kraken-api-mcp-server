from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def spot_public_server_time() -> dict[str, Any]:
        """Return the current Kraken Spot server time as both Unix timestamp and RFC 1123 string."""
        return await client.spot_public_get("/0/public/Time")

    @mcp.tool()
    async def spot_public_system_status() -> dict[str, Any]:
        """Return the current Kraken Spot system status and trading mode.

        Status values: 'online' (full trading), 'cancel_only', 'post_only',
        'limit_only', or 'maintenance'.
        """
        return await client.spot_public_get("/0/public/SystemStatus")

    @mcp.tool()
    async def spot_public_assets(
        asset: Annotated[str | None, "Comma-delimited asset names to filter (e.g. 'XBT,ETH'). Omit for all assets."] = None,
        aclass: Annotated[str | None, "Asset class filter. Default 'currency'."] = None,
    ) -> dict[str, Any]:
        """Return information about assets available on Kraken Spot.

        Each asset entry includes its display decimals, on-chain decimals,
        deposit/withdrawal status, and alt-name mappings.
        """
        return await client.spot_public_get("/0/public/Assets", {"asset": asset, "aclass": aclass})

    @mcp.tool()
    async def spot_public_asset_pairs(
        pair: Annotated[str | None, "Comma-delimited asset pair names to filter (e.g. 'XBTUSD,ETHUSD'). Omit for all pairs."] = None,
        info: Annotated[str | None, "Detail level: 'info' (default, full spec), 'leverage', 'fees', or 'margin'."] = None,
        country_code: Annotated[str | None, "ISO 3166-1 alpha-2 country code to filter pairs available in that jurisdiction."] = None,
    ) -> dict[str, Any]:
        """Return tradable asset pairs on Kraken Spot with their full specifications.

        Each pair includes lot/quote decimals, min/max order size, fee schedules,
        margin parameters, and status. Prefer the kraken-spot://asset-pairs resource
        for repeated reads (cached 1 h).
        """
        return await client.spot_public_get(
            "/0/public/AssetPairs",
            {"pair": pair, "info": info, "country_code": country_code},
        )

    @mcp.tool()
    async def spot_public_ticker(
        pair: Annotated[str, "Comma-delimited asset pair(s) (e.g. 'XBTUSD' or 'XBTUSD,ETHUSD')."],
    ) -> dict[str, Any]:
        """Return current ticker data for one or more Spot asset pairs.

        Each ticker includes best bid/ask, last trade price and volume,
        24-hour OHLC, volume, VWAP, trade count, and low/high.
        """
        return await client.spot_public_get("/0/public/Ticker", {"pair": pair})

    @mcp.tool()
    async def spot_public_ohlc(
        pair: Annotated[str, "Asset pair (e.g. 'XBTUSD')."],
        interval: Annotated[int, "Candle interval in minutes. Allowed: 1, 5, 15, 30, 60, 240, 1440, 10080, 21600."] = 1,
        since: Annotated[int | None, "Return OHLC data since this Unix timestamp. The last (current) bar is always incomplete."] = None,
    ) -> dict[str, Any]:
        """Return OHLC candle data for a Spot asset pair.

        Returns up to 720 bars. Prices are strings to preserve precision.
        The final bar in each response is the in-progress candle for the current period.
        """
        return await client.spot_public_get(
            "/0/public/OHLC",
            {"pair": pair, "interval": interval, "since": since},
        )

    @mcp.tool()
    async def spot_public_orderbook(
        pair: Annotated[str, "Asset pair (e.g. 'XBTUSD')."],
        count: Annotated[int, "Maximum number of bid/ask price levels to return (1–500)."] = 100,
    ) -> dict[str, Any]:
        """Return the current order book (level-2 depth) for a Spot asset pair.

        Each side is a list of [price, volume, timestamp] entries sorted by
        best price first. Prices and volumes are strings.
        """
        return await client.spot_public_get("/0/public/Depth", {"pair": pair, "count": count})

    @mcp.tool()
    async def spot_public_recent_trades(
        pair: Annotated[str, "Asset pair (e.g. 'XBTUSD')."],
        since: Annotated[str | None, "Return trades since this Unix timestamp or trade ID (exclusive)."] = None,
        count: Annotated[int | None, "Maximum number of trades to return (default 1000, max 1000)."] = None,
    ) -> dict[str, Any]:
        """Return recent public trades for a Spot asset pair.

        Each trade includes price, volume, timestamp, side ('b'/'s'),
        order type ('m'/'l'), and miscellaneous flags. Also returns the
        'last' ID to use as the next 'since' for pagination.
        """
        return await client.spot_public_get(
            "/0/public/Trades",
            {"pair": pair, "since": since, "count": count},
        )

    @mcp.tool()
    async def spot_public_recent_spreads(
        pair: Annotated[str, "Asset pair (e.g. 'XBTUSD')."],
        since: Annotated[int | None, "Return spread data since this Unix timestamp."] = None,
    ) -> dict[str, Any]:
        """Return recent bid/ask spread data for a Spot asset pair.

        Each entry is [timestamp, bid, ask]. Also returns 'last' for pagination.
        """
        return await client.spot_public_get(
            "/0/public/Spread",
            {"pair": pair, "since": since},
        )
