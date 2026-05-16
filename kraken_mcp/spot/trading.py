from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    def _check_trading() -> dict[str, Any] | None:
        if not cfg.trading_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRADING_ENABLED=true to enable trading tools")
        return None

    @mcp.tool()
    async def spot_trade_add_order(
        pair: Annotated[str, "Asset pair to trade (e.g. 'XBTUSD')."],
        type: Annotated[str, "Order direction: 'buy' or 'sell'."],
        ordertype: Annotated[str, "Order type: 'market', 'limit', 'stop-loss', 'take-profit', 'stop-loss-limit', 'take-profit-limit', 'trailing-stop', 'trailing-stop-limit', or 'settle-position'."],
        volume: Annotated[str, "Order volume in base asset lots (as a string to preserve precision)."],
        price: Annotated[str | None, "Primary price. Required for limit/stop-loss-limit/take-profit-limit orders; the trigger price for stop/trailing orders."] = None,
        price2: Annotated[str | None, "Secondary price. The limit price for stop-loss-limit and take-profit-limit orders."] = None,
        leverage: Annotated[str | None, "Margin leverage (e.g. '2', '3'). Omit for non-margin orders."] = None,
        reduce_only: Annotated[bool | None, "If true, only reduce an existing position; reject if it would open a new one."] = None,
        stptype: Annotated[str | None, "Self-trade prevention type: 'cancel-newest', 'cancel-oldest', or 'cancel-both'."] = None,
        oflags: Annotated[str | None, "Comma-delimited order flags: 'post' (post-only), 'fcib' (prefer fee in base), 'fciq' (prefer fee in quote), 'nompp' (no market price protection), 'viqc' (volume in quote currency)."] = None,
        timeinforce: Annotated[str | None, "Time-in-force: 'GTC' (good till cancelled, default), 'IOC' (immediate-or-cancel), or 'GTD' (good till date, requires expiretm)."] = None,
        starttm: Annotated[str | None, "Scheduled start time: 0=now (default), Unix timestamp, or '+<seconds>'."] = None,
        expiretm: Annotated[str | None, "Expiry time: 0=no expiry (default), Unix timestamp, or '+<seconds>'. Required for GTD."] = None,
        userref: Annotated[int | None, "User-defined integer reference ID attached to the order."] = None,
        cl_ord_id: Annotated[str | None, "Client order ID (max 32 alphanumeric chars). Must be unique."] = None,
        close_ordertype: Annotated[str | None, "Attached close order type (e.g. 'stop-loss-limit'). Triggers when the parent order fills."] = None,
        close_price: Annotated[str | None, "Trigger price for the attached close order."] = None,
        close_price2: Annotated[str | None, "Secondary price for the attached close order (for stop-loss-limit)."] = None,
        validate: Annotated[bool, "If true, validate inputs and return the would-be order description without submitting. Use for dry-runs."] = False,
    ) -> dict[str, Any]:
        """Place a new order on Kraken Spot. Requires KRAKEN_TRADING_ENABLED=true.

        All price and volume fields are strings to avoid floating-point rounding.
        Returns the order transaction ID(s) and a human-readable description.
        When validate=true no order is placed; use this to confirm parameters before execution.
        """
        if err := _check_trading():
            return err
        data: dict[str, Any] = {
            "pair": pair, "type": type, "ordertype": ordertype, "volume": volume,
            "price": price, "price2": price2, "leverage": leverage,
            "reduce_only": reduce_only, "stptype": stptype, "oflags": oflags,
            "timeinforce": timeinforce, "starttm": starttm, "expiretm": expiretm,
            "userref": userref, "cl_ord_id": cl_ord_id,
            "close[ordertype]": close_ordertype, "close[price]": close_price,
            "close[price2]": close_price2, "validate": validate,
        }
        return await client.spot_private_post("/0/private/AddOrder", data)

    @mcp.tool()
    async def spot_trade_add_order_batch(
        pair: Annotated[str, "Asset pair for all orders in the batch (e.g. 'XBTUSD')."],
        orders: Annotated[list[dict[str, Any]], "List of up to 15 order dicts. Each dict uses the same fields as spot_trade_add_order minus 'pair'."],
        deadline: Annotated[str | None, "RFC3339 timestamp after which the batch is rejected if not fully processed."] = None,
        validate: Annotated[bool, "Validate all orders without submitting any."] = False,
    ) -> dict[str, Any]:
        """Place a batch of up to 15 orders for a single asset pair atomically. Requires KRAKEN_TRADING_ENABLED=true.

        All orders must be for the same pair. Partial fills are possible; each order
        gets its own transaction ID in the response. Use validate=true for dry-runs.
        """
        if err := _check_trading():
            return err
        import json
        return await client.spot_private_post(
            "/0/private/AddOrderBatch",
            {"pair": pair, "orders": json.dumps(orders), "deadline": deadline, "validate": validate},
        )

    @mcp.tool()
    async def spot_trade_amend_order(
        txid: Annotated[str | None, "Transaction ID of the order to amend. Mutually exclusive with cl_ord_id."] = None,
        cl_ord_id: Annotated[str | None, "Client order ID of the order to amend. Mutually exclusive with txid."] = None,
        order_qty: Annotated[str | None, "New total order quantity. Must be >= any already-filled amount."] = None,
        display_qty: Annotated[str | None, "New iceberg display quantity (visible portion). Must be <= order_qty."] = None,
        limit_price: Annotated[str | None, "New limit price for limit orders."] = None,
        trigger_price: Annotated[str | None, "New trigger price for stop/take-profit orders."] = None,
        post_only: Annotated[bool | None, "If true, enforce post-only on the amended order."] = None,
        deadline: Annotated[str | None, "RFC3339 timestamp; reject amend if not processed by this time."] = None,
        validate: Annotated[bool, "Validate the amend without applying it."] = False,
    ) -> dict[str, Any]:
        """Amend an open Spot order in-place without cancel-and-replace. Requires KRAKEN_TRADING_ENABLED=true.

        In-place amendment preserves queue priority when only quantity is reduced.
        Changing price resets queue priority. Provide exactly one of txid or cl_ord_id.
        """
        if err := _check_trading():
            return err
        return await client.spot_private_post("/0/private/AmendOrder", {
            "txid": txid, "cl_ord_id": cl_ord_id, "order_qty": order_qty,
            "display_qty": display_qty, "limit_price": limit_price,
            "trigger_price": trigger_price, "post_only": post_only,
            "deadline": deadline, "validate": validate,
        })

    @mcp.tool()
    async def spot_trade_edit_order(
        txid: Annotated[str, "Transaction ID of the order to replace."],
        pair: Annotated[str, "Asset pair (must match the original order's pair)."],
        volume: Annotated[str | None, "New order volume. If omitted, original volume is kept."] = None,
        price: Annotated[str | None, "New primary price."] = None,
        price2: Annotated[str | None, "New secondary price (for stop-limit orders)."] = None,
        oflags: Annotated[str | None, "New order flags (replaces original flags entirely if set)."] = None,
        cancel_response: Annotated[bool | None, "If true, return the cancel response for the old order."] = None,
        userref: Annotated[int | None, "New user reference ID."] = None,
        deadline: Annotated[str | None, "RFC3339 deadline for processing."] = None,
        validate: Annotated[bool, "Validate without executing the edit."] = False,
    ) -> dict[str, Any]:
        """Cancel and replace an open Spot order (legacy EditOrder). Requires KRAKEN_TRADING_ENABLED=true.

        This is a cancel-and-replace; queue priority is not preserved.
        Prefer spot_trade_amend_order for in-place changes that keep priority.
        """
        if err := _check_trading():
            return err
        return await client.spot_private_post("/0/private/EditOrder", {
            "txid": txid, "pair": pair, "volume": volume, "price": price,
            "price2": price2, "oflags": oflags, "cancel_response": cancel_response,
            "userref": userref, "deadline": deadline, "validate": validate,
        })

    @mcp.tool()
    async def spot_trade_cancel_order(
        txid: Annotated[str | None, "Transaction ID of the order to cancel. Provide exactly one of txid or cl_ord_id."] = None,
        cl_ord_id: Annotated[str | None, "Client order ID of the order to cancel."] = None,
    ) -> dict[str, Any]:
        """Cancel a single open Spot order by transaction ID or client order ID. Requires KRAKEN_TRADING_ENABLED=true."""
        if err := _check_trading():
            return err
        return await client.spot_private_post("/0/private/CancelOrder", {"txid": txid, "cl_ord_id": cl_ord_id})

    @mcp.tool()
    async def spot_trade_cancel_all_orders(
        confirm: Annotated[bool, "Must be true to proceed. Returns an error without executing if false."] = False,
    ) -> dict[str, Any]:
        """Cancel ALL open Spot orders. Requires KRAKEN_TRADING_ENABLED=true AND confirm=true.

        This is irreversible. Double-check open positions before calling.
        Returns the count of cancelled orders.
        """
        if err := _check_trading():
            return err
        if not confirm:
            return error_response("confirmation_required", "Pass confirm=true to cancel all open spot orders")
        return await client.spot_private_post("/0/private/CancelAllOrders")

    @mcp.tool()
    async def spot_trade_cancel_all_orders_after(
        timeout: Annotated[int, "Seconds until all open orders are cancelled. Set to 0 to disable an active timer."],
    ) -> dict[str, Any]:
        """Set or disable the Spot dead-man's switch. Requires KRAKEN_TRADING_ENABLED=true.

        When active, Kraken cancels all open orders if the timer is not renewed before it expires.
        Call repeatedly with a fresh timeout to keep the switch alive. Set timeout=0 to disarm.
        """
        if err := _check_trading():
            return err
        return await client.spot_private_post("/0/private/CancelAllOrdersAfter", {"timeout": timeout})

    @mcp.tool()
    async def spot_trade_cancel_order_batch(
        orders: Annotated[list[str], "List of transaction IDs or client order IDs to cancel (max 50)."],
    ) -> dict[str, Any]:
        """Cancel up to 50 open Spot orders in a single request. Requires KRAKEN_TRADING_ENABLED=true.

        Returns counts of successfully cancelled and failed cancellations.
        Partial success is possible — some orders may fail if already filled or cancelled.
        """
        if err := _check_trading():
            return err
        import json
        return await client.spot_private_post("/0/private/CancelOrderBatch", {"orders": json.dumps(orders)})
