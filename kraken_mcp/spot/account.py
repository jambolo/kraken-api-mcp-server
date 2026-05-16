from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def spot_account_balance() -> dict[str, Any]:
        """Return all asset balances held in the Spot account, excluding credit/hold amounts.

        Balances are returned as strings (e.g. {"ZUSD": "1234.56", "XXBT": "0.5"}).
        Use spot_account_balance_ex for extended info including held and credit amounts.
        """
        return await client.spot_private_post("/0/private/Balance")

    @mcp.tool()
    async def spot_account_balance_ex() -> dict[str, Any]:
        """Return extended Spot account balances including hold, credit, and credit used amounts.

        Each entry includes 'balance', 'hold_trade', and optionally 'credit' / 'credit_used'.
        """
        return await client.spot_private_post("/0/private/BalanceEx")

    @mcp.tool()
    async def spot_account_trade_balance(
        asset: Annotated[str | None, "Base asset for margin calculations (default 'ZUSD'). Use Kraken's internal name (e.g. 'ZUSD', 'XXBT')."] = None,
    ) -> dict[str, Any]:
        """Return the Spot trade balance summary used for margin calculations.

        Includes equity, free margin, initial and used margin, unrealized P&L,
        and the cost basis of all open positions denominated in the base asset.
        """
        return await client.spot_private_post("/0/private/TradeBalance", {"asset": asset})

    @mcp.tool()
    async def spot_account_open_orders(
        trades: Annotated[bool | None, "If true, include the trade IDs associated with each order."] = None,
        userref: Annotated[int | None, "Filter results to orders with this user reference ID."] = None,
        cl_ord_id: Annotated[str | None, "Filter results to this client order ID."] = None,
    ) -> dict[str, Any]:
        """Return all currently open Spot orders with their full details.

        Each order includes status, description, volume, filled volume,
        current price, fee, and timestamps.
        """
        return await client.spot_private_post("/0/private/OpenOrders", {
            "trades": trades, "userref": userref, "cl_ord_id": cl_ord_id,
        })

    @mcp.tool()
    async def spot_account_closed_orders(
        trades: Annotated[bool | None, "If true, include associated trade IDs."] = None,
        userref: Annotated[int | None, "Filter to orders with this user reference ID."] = None,
        start: Annotated[str | None, "Start of time range: Unix timestamp or transaction ID (inclusive)."] = None,
        end: Annotated[str | None, "End of time range: Unix timestamp or transaction ID (inclusive)."] = None,
        ofs: Annotated[int | None, "Pagination offset (0-based)."] = None,
        closetime: Annotated[str | None, "Which timestamp to filter on: 'open', 'close', or 'both' (default 'both')."] = None,
        consolidate_taker: Annotated[bool | None, "If true, consolidate taker trades with their maker counterpart."] = None,
    ) -> dict[str, Any]:
        """Return closed Spot orders (filled, cancelled, expired) with pagination support.

        Results are sorted by close time descending. Use 'ofs' for pagination;
        the response includes 'count' (total matching) to determine page count.
        """
        return await client.spot_private_post("/0/private/ClosedOrders", {
            "trades": trades, "userref": userref, "start": start, "end": end,
            "ofs": ofs, "closetime": closetime, "consolidate_taker": consolidate_taker,
        })

    @mcp.tool()
    async def spot_account_query_orders(
        txid: Annotated[str, "Comma-delimited transaction IDs to look up (max 50)."],
        trades: Annotated[bool | None, "If true, include associated trade IDs in the response."] = None,
        userref: Annotated[int | None, "User reference ID filter (applied across all returned orders)."] = None,
        consolidate_taker: Annotated[bool | None, "Consolidate taker trades with maker counterpart."] = None,
    ) -> dict[str, Any]:
        """Return detailed info for specific Spot orders by transaction ID.

        Useful for looking up the status of recently placed orders. Can query
        both open and closed orders in a single call.
        """
        return await client.spot_private_post("/0/private/QueryOrders", {
            "txid": txid, "trades": trades, "userref": userref,
            "consolidate_taker": consolidate_taker,
        })

    @mcp.tool()
    async def spot_account_order_amends(
        txid: Annotated[str, "Transaction ID of the order to retrieve amendment history for."],
    ) -> dict[str, Any]:
        """Return the full amendment history for a Spot order.

        Each entry records what changed (price, qty), when, and the amendment ID.
        Only orders that have been amended at least once will have history.
        """
        return await client.spot_private_post("/0/private/OrderAmends", {"txid": txid})

    @mcp.tool()
    async def spot_account_trades_history(
        type: Annotated[str | None, "Trade type filter: 'all' (default), 'any position', 'closed position', 'closing position', or 'no position'."] = None,
        trades: Annotated[bool | None, "If true, include the trade IDs within each ledger entry."] = None,
        start: Annotated[str | None, "Start of range: Unix timestamp or trade ID."] = None,
        end: Annotated[str | None, "End of range: Unix timestamp or trade ID."] = None,
        ofs: Annotated[int | None, "Pagination offset."] = None,
        consolidate_taker: Annotated[bool | None, "Consolidate taker trades with their maker counterpart."] = None,
        ledgers: Annotated[bool | None, "If true, include associated ledger entries."] = None,
    ) -> dict[str, Any]:
        """Return trade execution history for the Spot account with pagination.

        Each trade entry includes the pair, price, volume, fee, cost,
        side, type, and whether it involved a margin position.
        """
        return await client.spot_private_post("/0/private/TradesHistory", {
            "type": type, "trades": trades, "start": start, "end": end,
            "ofs": ofs, "consolidate_taker": consolidate_taker, "ledgers": ledgers,
        })

    @mcp.tool()
    async def spot_account_query_trades(
        txid: Annotated[str, "Comma-delimited trade IDs to look up (max 20)."],
        trades: Annotated[bool | None, "If true, include related trade IDs in each entry."] = None,
    ) -> dict[str, Any]:
        """Return detailed info for specific Spot trade fills by trade ID.

        Returns the same fields as spot_account_trades_history but targeted
        at specific trade IDs. Use spot_account_open_orders to get trade IDs
        from in-flight orders.
        """
        return await client.spot_private_post("/0/private/QueryTrades", {
            "txid": txid, "trades": trades,
        })

    @mcp.tool()
    async def spot_account_open_positions(
        txid: Annotated[str | None, "Comma-delimited transaction IDs to restrict results to specific positions."] = None,
        docalcs: Annotated[bool | None, "If true, include current P&L calculations (adds latency). Default false."] = None,
        consolidation: Annotated[str | None, "Position consolidation method. Use 'market' to merge all positions per pair."] = None,
    ) -> dict[str, Any]:
        """Return all open Spot margin positions.

        Each entry includes the pair, direction, cost, fees, value, net P&L,
        and margin used. Set docalcs=true to include unrealized P&L at current market.
        """
        return await client.spot_private_post("/0/private/OpenPositions", {
            "txid": txid, "docalcs": docalcs, "consolidation": consolidation,
        })

    @mcp.tool()
    async def spot_account_ledgers(
        asset: Annotated[str | None, "Comma-delimited list of assets to filter (e.g. 'ZUSD,XXBT'). Default 'all'."] = None,
        aclass: Annotated[str | None, "Asset class filter. Default 'currency'."] = None,
        type: Annotated[str | None, "Ledger entry type: 'all', 'deposit', 'withdrawal', 'trade', 'margin', 'rollover', 'credit', 'transfer', 'settled', 'staking', 'dividend', 'sale', or 'nft'."] = None,
        start: Annotated[str | None, "Start of range: Unix timestamp or ledger ID."] = None,
        end: Annotated[str | None, "End of range: Unix timestamp or ledger ID."] = None,
        ofs: Annotated[int | None, "Pagination offset."] = None,
        without_count: Annotated[bool | None, "If true, omit the total count from the response for faster queries."] = None,
    ) -> dict[str, Any]:
        """Return ledger entries (accounting events) for the Spot account.

        Each entry includes the asset, amount, balance after, fee, and type.
        Cost: 2 counter units (higher than most endpoints). Use pagination for large histories.
        """
        return await client.spot_private_post("/0/private/Ledgers", {
            "asset": asset, "aclass": aclass, "type": type, "start": start,
            "end": end, "ofs": ofs, "without_count": without_count,
        })

    @mcp.tool()
    async def spot_account_query_ledgers(
        id: Annotated[str, "Comma-delimited ledger entry IDs to look up (max 20)."],
        trades: Annotated[bool | None, "If true, include associated trade IDs."] = None,
    ) -> dict[str, Any]:
        """Return detailed info for specific Spot ledger entries by ledger ID."""
        return await client.spot_private_post("/0/private/QueryLedgers", {
            "id": id, "trades": trades,
        })

    @mcp.tool()
    async def spot_account_trade_volume(
        pair: Annotated[str | None, "Comma-delimited asset pairs to include fee schedule data for. Omit for volume-only response."] = None,
    ) -> dict[str, Any]:
        """Return the 30-day trade volume (in USD) and current fee tier for the account.

        Includes the fee schedule with maker/taker rates at each volume breakpoint.
        Use this to determine when the account reaches the next fee tier.
        """
        return await client.spot_private_post("/0/private/TradeVolume", {"pair": pair})
