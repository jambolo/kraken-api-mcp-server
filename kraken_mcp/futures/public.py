from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def futures_public_tickers() -> dict[str, Any]:
        """Return current ticker data for all Kraken Futures symbols.

        Each ticker includes last price, bid/ask, 24-hour volume, open interest,
        mark price, funding rate, and index price. Prefer the
        kraken-futures://tickers resource for repeated reads (cached 5s).
        """
        return await client.futures_public_get("/derivatives/api/v3/tickers")

    @mcp.tool()
    async def futures_public_ticker(
        symbol: Annotated[str, "Futures symbol (e.g. 'PI_XBTUSD' for BTC perpetual, 'FI_ETHUSD_250328' for a dated future)."],
    ) -> dict[str, Any]:
        """Return the current ticker for a specific Kraken Futures symbol.

        Includes last price, mark price, best bid/ask with sizes, 24-hour volume,
        open interest, funding rate, and index price.
        """
        return await client.futures_public_get(f"/derivatives/api/v3/tickers/{symbol}")

    @mcp.tool()
    async def futures_public_instruments() -> dict[str, Any]:
        """Return all Kraken Futures instruments and their full specifications.

        Each instrument includes contract size, tick size, max leverage, trading status,
        margin requirements, and funding parameters. Prefer the
        kraken-futures://instruments resource for repeated reads (cached 5 min).
        """
        return await client.futures_public_get("/derivatives/api/v3/instruments")

    @mcp.tool()
    async def futures_public_instruments_trading() -> dict[str, Any]:
        """Return only actively tradable Kraken Futures instruments.

        A subset of futures_public_instruments filtered to status='trading'.
        Use this when building an order form to avoid listing suspended instruments.
        """
        return await client.futures_public_get("/derivatives/api/v3/instruments/trading")

    @mcp.tool()
    async def futures_public_instrument_status_list() -> dict[str, Any]:
        """Return the trading status for all Kraken Futures instruments.

        Status values include 'trading', 'suspended', 'cancel_only', and 'post_only'.
        Prefer the kraken-futures://instrument-status resource for repeated reads (cached 30s).
        """
        return await client.futures_public_get("/derivatives/api/v3/instruments/status")

    @mcp.tool()
    async def futures_public_instrument_status(
        symbol: Annotated[str, "Futures symbol to check status for (e.g. 'PI_XBTUSD')."],
    ) -> dict[str, Any]:
        """Return the current trading status for a specific Kraken Futures instrument.

        Returns the instrument's status ('trading', 'suspended', 'cancel_only', 'post_only'),
        and any active trading restrictions or maintenance windows.
        """
        return await client.futures_public_get(f"/derivatives/api/v3/instruments/{symbol}/status")

    @mcp.tool()
    async def futures_public_orderbook(
        symbol: Annotated[str, "Futures symbol to fetch the order book for (e.g. 'PI_XBTUSD')."],
    ) -> dict[str, Any]:
        """Return the current level-2 order book for a Kraken Futures symbol.

        Returns bid and ask arrays with price, size, and cumulative size.
        For a live streaming order book, use fws_subscribe_book instead.
        """
        return await client.futures_public_get("/derivatives/api/v3/orderbook", {"symbol": symbol})

    @mcp.tool()
    async def futures_public_history(
        symbol: Annotated[str, "Futures symbol (e.g. 'PI_XBTUSD')."],
        lastTime: Annotated[str | None, "ISO 8601 timestamp; return trades executed after this time. Omit for the most recent trades."] = None,
    ) -> dict[str, Any]:
        """Return public trade execution history for a Kraken Futures symbol.

        Each trade includes price, size, side, and execution timestamp.
        Use lastTime for pagination through historical data.
        """
        return await client.futures_public_get("/derivatives/api/v3/history", {
            "symbol": symbol, "lastTime": lastTime,
        })

    @mcp.tool()
    async def futures_public_funding_rates(
        symbol: Annotated[str, "Perpetual futures symbol (e.g. 'PI_XBTUSD'). Dated futures do not have funding rates."],
    ) -> dict[str, Any]:
        """Return historical funding rate data for a Kraken perpetual futures symbol.

        Each entry includes the funding rate, relative funding rate, funding rate
        prediction, and the funding timestamp. Useful for calculating the cost
        of holding a perpetual position over time.
        """
        return await client.futures_public_get(
            "/derivatives/api/v3/historical-funding-rates",
            {"symbol": symbol},
        )

    # ── Charts ────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def futures_chart_tick_types() -> dict[str, Any]:
        """Return all available chart tick types for Kraken Futures.

        Common types: 'trade' (executed prices), 'mark' (mark price),
        'spot' (index price). Use these as the tick_type parameter in other chart tools.
        """
        return await client.futures_public_get("/api/charts/v1/")

    @mcp.tool()
    async def futures_chart_symbols(
        tick_type: Annotated[str, "Chart tick type (e.g. 'trade', 'mark', 'spot'). From futures_chart_tick_types."],
    ) -> dict[str, Any]:
        """Return all symbols available for a given chart tick type.

        Use the returned symbols with futures_chart_resolutions and futures_chart_candles.
        """
        return await client.futures_public_get(f"/api/charts/v1/{tick_type}")

    @mcp.tool()
    async def futures_chart_resolutions(
        tick_type: Annotated[str, "Chart tick type (e.g. 'trade', 'mark')."],
        symbol: Annotated[str, "Futures symbol (e.g. 'PI_XBTUSD')."],
    ) -> dict[str, Any]:
        """Return available candle resolutions for a Futures symbol and tick type.

        Resolution strings (e.g. '1m', '5m', '15m', '1h', '4h', '1d') are used
        as the resolution parameter in futures_chart_candles.
        """
        return await client.futures_public_get(f"/api/charts/v1/{tick_type}/{symbol}")

    @mcp.tool()
    async def futures_chart_candles(
        tick_type: Annotated[str, "Chart tick type (e.g. 'trade' for executed prices, 'mark' for mark price OHLC)."],
        symbol: Annotated[str, "Futures symbol (e.g. 'PI_XBTUSD')."],
        resolution: Annotated[str, "Candle resolution string (e.g. '1m', '5m', '15m', '1h', '4h', '1d', '1w'). From futures_chart_resolutions."],
        from_: Annotated[int | None, "Start of range as Unix timestamp (seconds). Omit for the most recent candles."] = None,
        to: Annotated[int | None, "End of range as Unix timestamp (seconds). Omit for current time."] = None,
    ) -> dict[str, Any]:
        """Return OHLCV candle data for a Kraken Futures symbol.

        Each candle includes open, high, low, close prices and volume.
        Prices are numbers (not strings). Use tick_type='mark' for mark-price charts
        and tick_type='trade' for trade-price charts.
        """
        params: dict[str, Any] = {}
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        return await client.futures_public_get(
            f"/api/charts/v1/{tick_type}/{symbol}/{resolution}", params
        )

    @mcp.tool()
    async def futures_chart_liquidity_pool(
        symbol: Annotated[str | None, "Futures symbol to filter analytics to. Omit for all symbols."] = None,
    ) -> dict[str, Any]:
        """Return liquidity pool analytics for Kraken Futures.

        Includes pool size, utilization, available liquidity, and fee metrics.
        Useful for understanding market depth beyond the order book.
        """
        return await client.futures_public_get(
            "/api/charts/v1/analytics/liquidity-pool",
            {"symbol": symbol} if symbol else None,
        )

    @mcp.tool()
    async def futures_chart_analytics(
        symbol: Annotated[str, "Futures symbol to retrieve analytics for (e.g. 'PI_XBTUSD')."],
        analytics_type: Annotated[str, "Analytics series to fetch (e.g. 'oi' for open interest, 'premium' for basis premium)."],
    ) -> dict[str, Any]:
        """Return a specific analytics time series for a Kraken Futures symbol.

        Common analytics types: 'oi' (open interest over time), 'premium'
        (mark vs index basis). Use futures_chart_tick_types to discover all
        available analytics_type values.
        """
        return await client.futures_public_get(f"/api/charts/v1/analytics/{symbol}/{analytics_type}")
