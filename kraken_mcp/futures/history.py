from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient

_HISTORY_PARAMS = "before, since, sort, and continuation_token are all optional pagination controls."


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def futures_history_executions(
        before: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp < this value."] = None,
        continuation_token: Annotated[str | None, "Opaque pagination token returned in a previous response. Use to fetch the next page."] = None,
        since: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp >= this value."] = None,
        sort: Annotated[str | None, "Sort order: 'asc' (oldest first) or 'desc' (newest first, default)."] = None,
        tradeable: Annotated[str | None, "Filter results to a specific symbol (e.g. 'PI_XBTUSD')."] = None,
    ) -> dict[str, Any]:
        """Return private execution (fill) history for the Futures account from /api/history/v3.

        Each entry includes symbol, side, price, quantity, fee, fill type,
        and timestamp. Supports forward and backward pagination via continuation_token.
        For real-time fills use fws_subscribe_fills instead.
        """
        return await client.futures_private_get("/api/history/v3/executions", {
            "before": before, "continuation_token": continuation_token,
            "since": since, "sort": sort, "tradeable": tradeable,
        })

    @mcp.tool()
    async def futures_history_orders(
        before: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp < this value."] = None,
        continuation_token: Annotated[str | None, "Pagination token from a previous response."] = None,
        since: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp >= this value."] = None,
        sort: Annotated[str | None, "Sort order: 'asc' or 'desc' (default)."] = None,
        tradeable: Annotated[str | None, "Filter to a specific symbol (e.g. 'PI_XBTUSD')."] = None,
    ) -> dict[str, Any]:
        """Return private order history for the Futures account from /api/history/v3.

        Includes all order states: filled, partially filled, cancelled, and expired.
        Each entry records the order's full lifecycle with timestamps.
        """
        return await client.futures_private_get("/api/history/v3/orders", {
            "before": before, "continuation_token": continuation_token,
            "since": since, "sort": sort, "tradeable": tradeable,
        })

    @mcp.tool()
    async def futures_history_triggers(
        before: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp < this value."] = None,
        continuation_token: Annotated[str | None, "Pagination token from a previous response."] = None,
        since: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp >= this value."] = None,
        sort: Annotated[str | None, "Sort order: 'asc' or 'desc' (default)."] = None,
        tradeable: Annotated[str | None, "Filter to a specific symbol."] = None,
    ) -> dict[str, Any]:
        """Return trigger order event history (stop/take-profit activations) from /api/history/v3.

        Each entry records when a trigger order was activated, the trigger price,
        and the resulting market/limit order ID.
        """
        return await client.futures_private_get("/api/history/v3/triggers", {
            "before": before, "continuation_token": continuation_token,
            "since": since, "sort": sort, "tradeable": tradeable,
        })

    @mcp.tool()
    async def futures_history_public_executions(
        tradeable: Annotated[str, "Futures symbol to retrieve public execution history for (e.g. 'PI_XBTUSD')."],
        before: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp < this value."] = None,
        continuation_token: Annotated[str | None, "Pagination token from a previous response."] = None,
        since: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp >= this value."] = None,
        sort: Annotated[str | None, "Sort order: 'asc' or 'desc' (default)."] = None,
    ) -> dict[str, Any]:
        """Return public trade execution history for a Futures symbol from /api/history/v3.

        No authentication required. Returns the public trade tape with price,
        size, side, and timestamp for each trade.
        """
        return await client.futures_public_get(
            f"/api/history/v3/market/{tradeable}/executions",
            {"before": before, "continuation_token": continuation_token,
             "since": since, "sort": sort},
        )

    @mcp.tool()
    async def futures_history_public_orders(
        tradeable: Annotated[str, "Futures symbol to retrieve public order history for (e.g. 'PI_XBTUSD')."],
        before: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp < this value."] = None,
        continuation_token: Annotated[str | None, "Pagination token from a previous response."] = None,
        since: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp >= this value."] = None,
        sort: Annotated[str | None, "Sort order: 'asc' or 'desc' (default)."] = None,
    ) -> dict[str, Any]:
        """Return public order book event history for a Futures symbol from /api/history/v3.

        Records order placements, modifications, and cancellations on the public book.
        No authentication required.
        """
        return await client.futures_public_get(
            f"/api/history/v3/market/{tradeable}/orders",
            {"before": before, "continuation_token": continuation_token,
             "since": since, "sort": sort},
        )

    @mcp.tool()
    async def futures_history_public_price(
        tradeable: Annotated[str, "Futures symbol to retrieve price history for (e.g. 'PI_XBTUSD')."],
        before: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp < this value."] = None,
        continuation_token: Annotated[str | None, "Pagination token from a previous response."] = None,
        since: Annotated[str | None, "ISO 8601 timestamp; return records with timestamp >= this value."] = None,
        sort: Annotated[str | None, "Sort order: 'asc' or 'desc' (default)."] = None,
    ) -> dict[str, Any]:
        """Return public mark/index price history for a Futures symbol from /api/history/v3.

        Provides the time series of mark price and index price.
        No authentication required. Use futures_chart_candles for OHLCV aggregations.
        """
        return await client.futures_public_get(
            f"/api/history/v3/market/{tradeable}/price",
            {"before": before, "continuation_token": continuation_token,
             "since": since, "sort": sort},
        )
