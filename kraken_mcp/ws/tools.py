from __future__ import annotations

import time
from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from .client import FuturesWSClient
from .state import WSState


def register(mcp: Any, cfg: Config, ws_client: FuturesWSClient, state: WSState) -> None:

    async def _ensure_started() -> None:
        await ws_client.start()
        await ws_client.wait_ready(timeout=15.0)

    # ── Public subscriptions ──────────────────────────────────────────────────

    @mcp.tool()
    async def fws_subscribe_book(
        product_ids: Annotated[list[str], "Futures symbols to subscribe to (e.g. ['PI_XBTUSD', 'PF_ETHUSD']). Each symbol gets its own L2 book maintained in server-side cache."],
    ) -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket order book feed for one or more symbols.

        The server applies incoming book snapshots and deltas to maintain an up-to-date
        L2 book per symbol. Read the current book via the kraken-futures-ws://book/{symbol}
        resource or fws_snapshot tool. No authentication required.
        """
        await _ensure_started()
        await ws_client.subscribe("book", product_ids=product_ids)
        return {"status": "subscribed", "feed": "book", "product_ids": product_ids}

    @mcp.tool()
    async def fws_subscribe_ticker(
        product_ids: Annotated[list[str], "Futures symbols to subscribe to (e.g. ['PI_XBTUSD'])."],
    ) -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket full ticker feed.

        Provides mark price, bid/ask, last trade, funding rate, open interest,
        and 24-hour volume per symbol. Latest value is cached (last-message-wins).
        Read via kraken-futures-ws://ticker/{symbol} or fws_snapshot. No auth required.
        """
        await _ensure_started()
        await ws_client.subscribe("ticker", product_ids=product_ids)
        return {"status": "subscribed", "feed": "ticker", "product_ids": product_ids}

    @mcp.tool()
    async def fws_subscribe_ticker_lite(
        product_ids: Annotated[list[str], "Futures symbols to subscribe to."],
    ) -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket ticker_lite feed (reduced payload).

        A lightweight alternative to the full ticker — fewer fields, lower bandwidth.
        Suitable when only last price and bid/ask are needed. No auth required.
        """
        await _ensure_started()
        await ws_client.subscribe("ticker_lite", product_ids=product_ids)
        return {"status": "subscribed", "feed": "ticker_lite", "product_ids": product_ids}

    @mcp.tool()
    async def fws_subscribe_trade(
        product_ids: Annotated[list[str], "Futures symbols to subscribe to."],
    ) -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket public trade tape.

        Each message contains executed price, size, side, and timestamp.
        Messages are stored in a ring buffer (last 1000 per symbol).
        Use fws_drain to retrieve and clear buffered trades. No auth required.
        """
        await _ensure_started()
        await ws_client.subscribe("trade", product_ids=product_ids)
        return {"status": "subscribed", "feed": "trade", "product_ids": product_ids}

    @mcp.tool()
    async def fws_subscribe_heartbeat() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket heartbeat feed.

        Heartbeats arrive approximately every second and confirm the connection
        is alive. The last heartbeat timestamp is exposed via fws_status.
        No authentication required.
        """
        await _ensure_started()
        await ws_client.subscribe("heartbeat")
        return {"status": "subscribed", "feed": "heartbeat"}

    # ── Private subscriptions ─────────────────────────────────────────────────

    @mcp.tool()
    async def fws_subscribe_open_orders() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket open_orders private feed.

        Streams real-time updates for all open orders: placements, fills,
        partial fills, cancellations, and amendments. The latest state is cached
        (last-message-wins) and readable via fws_snapshot or the
        kraken-futures-ws://open-orders resource. Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("open_orders", private=True)
        return {"status": "subscribed", "feed": "open_orders"}

    @mcp.tool()
    async def fws_subscribe_open_orders_verbose() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket open_orders_verbose private feed.

        Like open_orders but includes additional fields: order type, limit price,
        stop price, reduce-only flag, and client order ID. Use when you need the
        full order spec in addition to fill updates. Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("open_orders_verbose", private=True)
        return {"status": "subscribed", "feed": "open_orders_verbose"}

    @mcp.tool()
    async def fws_subscribe_fills(
        product_ids: Annotated[list[str] | None, "Optional list of symbols to filter fill notifications to. Omit to receive fills across all symbols."] = None,
    ) -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket fills (execution) private feed.

        Each fill message contains symbol, side, price, quantity, fee, and timestamp.
        Messages accumulate in a ring buffer (last 1000). Use fws_drain to retrieve
        and clear buffered fills. Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("fills", product_ids=product_ids, private=True)
        return {"status": "subscribed", "feed": "fills", "product_ids": product_ids}

    @mcp.tool()
    async def fws_subscribe_open_positions() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket open_positions private feed.

        Streams position updates whenever a fill changes position size, side, or
        average entry price. The latest state is cached and readable via
        kraken-futures-ws://open-positions or fws_snapshot. Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("open_positions", private=True)
        return {"status": "subscribed", "feed": "open_positions"}

    @mcp.tool()
    async def fws_subscribe_balances() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket balances private feed.

        Streams real-time balance updates whenever fills, transfers, or funding
        payments change account balances. Readable via kraken-futures-ws://balances
        or fws_snapshot. Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("balances", private=True)
        return {"status": "subscribed", "feed": "balances"}

    @mcp.tool()
    async def fws_subscribe_account_log() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket account_log private feed.

        Streams a chronological ledger of account events: funding payments,
        liquidations, transfers, realized PnL settlements, and fee credits.
        Messages accumulate in a ring buffer (last 1000). Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("account_log", private=True)
        return {"status": "subscribed", "feed": "account_log"}

    @mcp.tool()
    async def fws_subscribe_notifications() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket notifications_auth private feed.

        Receives account-specific platform notifications: margin call warnings,
        liquidation alerts, system messages, and assignment events.
        Messages accumulate in a ring buffer (last 1000). Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("notifications_auth", private=True)
        return {"status": "subscribed", "feed": "notifications_auth"}

    @mcp.tool()
    async def fws_subscribe_deposits_withdrawals() -> dict[str, Any]:
        """Subscribe to the Kraken Futures WebSocket deposits_withdrawals private feed.

        Streams incoming deposit confirmations and outgoing withdrawal events
        for the Futures account. Messages accumulate in a ring buffer (last 1000).
        Requires Futures API credentials.
        """
        if not cfg.has_futures_auth:
            return error_response("not_configured", "Futures API key/secret not configured")
        await _ensure_started()
        await ws_client.subscribe("deposits_withdrawals", private=True)
        return {"status": "subscribed", "feed": "deposits_withdrawals"}

    # ── Control tools ─────────────────────────────────────────────────────────

    @mcp.tool()
    async def fws_unsubscribe(
        feed: Annotated[str, "Feed name to unsubscribe from (e.g. 'ticker', 'book', 'fills', 'open_orders')."],
        product_ids: Annotated[list[str] | None, "For symbol-specific feeds, the symbols to unsubscribe. Omit for account-wide feeds (e.g. 'open_orders', 'balances')."] = None,
    ) -> dict[str, Any]:
        """Unsubscribe from a Kraken Futures WebSocket feed.

        Sends an unsubscribe message over the WebSocket and removes the subscription
        from the server's tracking list. The cached state is retained until the
        process exits or new messages overwrite it.
        """
        await ws_client.unsubscribe(feed, product_ids=product_ids)
        return {"status": "unsubscribed", "feed": feed, "product_ids": product_ids}

    @mcp.tool()
    async def fws_list_subscriptions() -> dict[str, Any]:
        """Return all active Kraken Futures WebSocket subscriptions and their buffer queue depths.

        Each entry includes the feed name, product ID (if applicable), and for
        ring-buffer feeds, the number of messages currently buffered.
        """
        return {"subscriptions": state.list_subscriptions()}

    @mcp.tool()
    async def fws_snapshot(
        feed: Annotated[str, "Feed name to read (e.g. 'ticker', 'book', 'open_orders', 'balances', 'fills')."],
        product_id: Annotated[str | None, "Symbol for symbol-specific feeds (e.g. 'PI_XBTUSD'). Omit for account-wide feeds."] = None,
    ) -> dict[str, Any]:
        """Return the latest cached state for a subscribed Kraken Futures WebSocket feed.

        For last-message-wins feeds (ticker, open_orders, balances, open_positions):
        returns the most recent message. For ring-buffer feeds (fills, trade, account_log):
        returns all buffered messages without clearing. For book: returns the full
        sorted L2 snapshot. Returns {status: 'not-subscribed'} if not yet subscribed.
        """
        return state.snapshot(feed, product_id or "")

    @mcp.tool()
    async def fws_drain(
        feed: Annotated[str, "Feed name to drain (e.g. 'fills', 'trade', 'account_log', 'notifications_auth')."],
        product_id: Annotated[str | None, "Symbol for symbol-specific feeds. Omit for account-wide feeds."] = None,
        max: Annotated[int, "Maximum number of messages to return. The oldest messages beyond this limit are discarded."] = 1000,
    ) -> dict[str, Any]:
        """Return and clear buffered messages for a Kraken Futures WebSocket ring-buffer feed.

        Retrieves up to max messages from the buffer and clears them, enabling
        a 'pull what happened since last check' pattern. Returns count and messages.
        For book feeds, behaves like fws_snapshot (returns snapshot, does not clear).
        """
        messages = state.drain(feed, product_id or "", max)
        return {"feed": feed, "product_id": product_id, "count": len(messages), "messages": messages}

    @mcp.tool()
    async def fws_status() -> dict[str, Any]:
        """Return the current Kraken Futures WebSocket connection status and diagnostics.

        Includes: whether the connection is active, total reconnect count,
        seconds since the last heartbeat, the environment ('live'/'demo'),
        and the WebSocket URL in use.
        """
        now = time.monotonic()
        hb = ws_client.last_heartbeat
        return {
            "connected": ws_client.is_connected,
            "reconnect_count": ws_client.reconnect_count,
            "last_heartbeat_ago_s": round(now - hb, 1) if hb > 0 else None,
            "futures_env": cfg.futures_env,
            "ws_url": cfg.futures_ws_url,
        }

    @mcp.tool()
    async def fws_close() -> dict[str, Any]:
        """Disconnect the Kraken Futures WebSocket connection.

        Stops the background connection task and closes the socket.
        All cached state is retained in memory until the process exits.
        Subscriptions will be replayed automatically if the connection is restarted
        by calling any subscribe tool again.
        """
        await ws_client.stop()
        return {"status": "closed"}
