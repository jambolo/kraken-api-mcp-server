from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    def _check_trading() -> dict[str, Any] | None:
        if not cfg.trading_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRADING_ENABLED=true to enable futures trading tools")
        return None

    @mcp.tool()
    async def futures_trade_send_order(
        orderType: Annotated[str, "Order type: 'lmt' (limit), 'post' (post-only limit), 'ioc' (immediate-or-cancel), 'mkt' (market), 'stp' (stop), 'take_profit', or 'trailing_stop'."],
        symbol: Annotated[str, "Futures symbol to trade (e.g. 'PI_XBTUSD' for BTC perpetual)."],
        side: Annotated[str, "Order direction: 'buy' or 'sell'."],
        size: Annotated[float, "Order size in contracts (not USD notional). Check instrument spec for contract value."],
        limitPrice: Annotated[float | None, "Limit price. Required for 'lmt', 'post', 'ioc', and the limit leg of 'stp'/'take_profit'."] = None,
        stopPrice: Annotated[float | None, "Stop/trigger price. Required for 'stp' and 'take_profit' order types."] = None,
        clientOrderId: Annotated[str | None, "Client-assigned order ID (max 100 chars). Must be unique per account."] = None,
        reduceOnly: Annotated[bool | None, "If true, the order can only reduce an existing position; rejected if it would open or increase one."] = None,
        triggerSignal: Annotated[str | None, "Price signal used to trigger stop/trailing orders: 'mark' (default), 'spot', or 'last'."] = None,
        trailingStopDeviationUnit: Annotated[str | None, "Unit for trailing stop distance: 'PERCENT' or 'QUOTE_CURRENCY'. Required for trailing_stop orders."] = None,
        trailingStopMaxDeviation: Annotated[float | None, "Maximum trailing distance in the chosen unit. Required for trailing_stop orders."] = None,
    ) -> dict[str, Any]:
        """Send a new order to Kraken Futures. Requires KRAKEN_TRADING_ENABLED=true.

        Returns the order ID and status ('placed', 'partiallyFilled', 'filled', etc.).
        For position-reducing orders, set reduceOnly=true to prevent accidental position flips.
        Use futures_account_initial_margin to validate margin before calling this tool.
        """
        if err := _check_trading():
            return err
        return await client.futures_private_post("/derivatives/api/v3/sendorder", {
            "orderType": orderType, "symbol": symbol, "side": side, "size": size,
            "limitPrice": limitPrice, "stopPrice": stopPrice,
            "clientOrderId": clientOrderId, "reduceOnly": reduceOnly,
            "triggerSignal": triggerSignal,
            "trailingStopDeviationUnit": trailingStopDeviationUnit,
            "trailingStopMaxDeviation": trailingStopMaxDeviation,
        })

    @mcp.tool()
    async def futures_trade_edit_order(
        orderId: Annotated[str | None, "Kraken-assigned order ID. Provide exactly one of orderId or clientOrderId."] = None,
        clientOrderId: Annotated[str | None, "Client-assigned order ID. Provide exactly one of orderId or clientOrderId."] = None,
        size: Annotated[float | None, "New order size in contracts. Omit to keep current size."] = None,
        limitPrice: Annotated[float | None, "New limit price. Omit to keep current price."] = None,
        stopPrice: Annotated[float | None, "New stop/trigger price. Omit to keep current price."] = None,
    ) -> dict[str, Any]:
        """Edit the size or price of an open Kraken Futures order. Requires KRAKEN_TRADING_ENABLED=true.

        At least one of size, limitPrice, or stopPrice must be provided.
        Editing resets queue priority for the affected order.
        """
        if err := _check_trading():
            return err
        return await client.futures_private_post("/derivatives/api/v3/editorder", {
            "orderId": orderId, "clientOrderId": clientOrderId,
            "size": size, "limitPrice": limitPrice, "stopPrice": stopPrice,
        })

    @mcp.tool()
    async def futures_trade_cancel_order(
        order_id: Annotated[str | None, "Kraken-assigned order ID. Provide exactly one of order_id or cliOrdId."] = None,
        cliOrdId: Annotated[str | None, "Client-assigned order ID. Provide exactly one of order_id or cliOrdId."] = None,
    ) -> dict[str, Any]:
        """Cancel a single open Kraken Futures order. Requires KRAKEN_TRADING_ENABLED=true."""
        if err := _check_trading():
            return err
        return await client.futures_private_post("/derivatives/api/v3/cancelorder", {
            "order_id": order_id, "cliOrdId": cliOrdId,
        })

    @mcp.tool()
    async def futures_trade_cancel_all_orders(
        symbol: Annotated[str | None, "If provided, cancel only orders for this symbol. Omit to cancel all open orders across all symbols."] = None,
        confirm: Annotated[bool, "Must be true to proceed. Returns an error without executing if false."] = False,
    ) -> dict[str, Any]:
        """Cancel all open Kraken Futures orders. Requires KRAKEN_TRADING_ENABLED=true AND confirm=true.

        This is irreversible. When symbol is omitted, ALL open orders across ALL
        instruments are cancelled. Verify open positions before calling.
        """
        if err := _check_trading():
            return err
        if not confirm:
            return error_response("confirmation_required", "Pass confirm=true to cancel all open futures orders")
        return await client.futures_private_post("/derivatives/api/v3/cancelallorders", {"symbol": symbol})

    @mcp.tool()
    async def futures_trade_cancel_all_after(
        timeout: Annotated[int, "Seconds until all open orders are cancelled. Set to 0 to disarm an active timer."],
    ) -> dict[str, Any]:
        """Set or disable the Kraken Futures dead-man's switch. Requires KRAKEN_TRADING_ENABLED=true.

        Kraken cancels all open orders if this timer is not refreshed before expiry.
        Call repeatedly (e.g. every 30s with timeout=60) to maintain the switch.
        Set timeout=0 to disarm. Returns the current timer expiry time.
        """
        if err := _check_trading():
            return err
        return await client.futures_private_post("/derivatives/api/v3/cancelallordersafter", {"timeout": timeout})

    @mcp.tool()
    async def futures_trade_batch_order(
        batchOrder: Annotated[list[dict[str, Any]], "List of order operations. Each dict must have an 'order' key set to 'send', 'edit', or 'cancel', plus the relevant fields for that operation."],
    ) -> dict[str, Any]:
        """Execute multiple Futures order operations (send/edit/cancel) in a single atomic request. Requires KRAKEN_TRADING_ENABLED=true.

        Operations are processed in order. If any operation fails, subsequent operations
        may still be applied (not transactional). Returns per-operation results.
        Maximum batch size is determined by Kraken's API limits.
        """
        if err := _check_trading():
            return err
        import json
        return await client.futures_private_post("/derivatives/api/v3/batchorder", {
            "json": json.dumps({"batchOrder": batchOrder}),
        })

    @mcp.tool()
    async def futures_trade_open_orders() -> dict[str, Any]:
        """Return all currently open Kraken Futures orders for the account.

        Each order includes the symbol, side, order type, size, limit/stop price,
        filled size, status, creation time, and client order ID if set.
        """
        return await client.futures_private_get("/derivatives/api/v3/openorders")

    @mcp.tool()
    async def futures_trade_orders_status(
        orderIds: Annotated[list[str], "List of Kraken-assigned order IDs to query status for."],
    ) -> dict[str, Any]:
        """Return the current status of specific Kraken Futures orders by order ID.

        Returns the same fields as futures_trade_open_orders but targeted at
        specific orders. Works for both open and recently filled/cancelled orders.
        """
        import json
        return await client.futures_private_post("/derivatives/api/v3/orders/status", {
            "orderIds": json.dumps(orderIds),
        })
