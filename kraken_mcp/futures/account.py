from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def futures_account_get() -> dict:
        """Return the Kraken Futures account summary including balances and margin state.

        Includes cash account balance, margin account balances per collateral type,
        available margin, initial and maintenance margin used, portfolio value,
        and PnL in each configured currency.
        """
        return await client.futures_private_get("/derivatives/api/v3/accounts")

    @mcp.tool()
    async def futures_account_open_positions() -> dict:
        """Return all open Kraken Futures positions held by the account.

        Each position includes symbol, side, size, entry price, mark price,
        unrealised PnL, funding accrued, liquidation price, and initial margin used.
        """
        return await client.futures_private_get("/derivatives/api/v3/openpositions")

    @mcp.tool()
    async def futures_account_unwind_queue() -> dict:
        """Return the auto-deleveraging (ADL) unwind queue for the Futures account.

        Positions appear in the queue when the account is near the insurance fund trigger.
        Higher queue position means higher deleveraging priority.
        """
        return await client.futures_private_get("/derivatives/api/v3/unwindqueue")

    @mcp.tool()
    async def futures_account_initial_margin(
        symbol: Annotated[str, "Futures symbol to calculate margin for (e.g. 'PI_XBTUSD')."],
        side: Annotated[str, "Order side: 'buy' or 'sell'."],
        orderType: Annotated[str, "Order type: 'lmt', 'post', 'ioc', 'mkt', 'stp', or 'take_profit'."],
        size: Annotated[float, "Proposed order size in contracts."],
        limitPrice: Annotated[float | None, "Limit price for limit/stop-limit orders. Required when orderType is 'lmt', 'post', or 'ioc'."] = None,
    ) -> dict:
        """Calculate the initial margin required for a hypothetical Futures order.

        Use this before futures_trade_send_order to verify the account has sufficient
        margin. Returns the required initial margin and whether it exceeds available balance.
        This does not place any order.
        """
        return await client.futures_private_get("/derivatives/api/v3/initialmargin", {
            "symbol": symbol, "side": side, "orderType": orderType,
            "size": size, "limitPrice": limitPrice,
        })

    @mcp.tool()
    async def futures_account_max_order_size(
        symbol: Annotated[str, "Futures symbol (e.g. 'PI_XBTUSD')."],
        side: Annotated[str, "Order side: 'buy' or 'sell'."],
        orderType: Annotated[str, "Order type: 'lmt', 'post', 'ioc', 'mkt', 'stp', or 'take_profit'."],
        limitPrice: Annotated[float | None, "Limit price. Required for limit order types."] = None,
    ) -> dict:
        """Return the maximum order size the account can place given current margin availability.

        Useful for sizing the largest allowable position before calling
        futures_trade_send_order. Takes the current leverage preference into account.
        """
        return await client.futures_private_get("/derivatives/api/v3/initialmargin/maxordersize", {
            "symbol": symbol, "side": side, "orderType": orderType,
            "limitPrice": limitPrice,
        })

    @mcp.tool()
    async def futures_account_notifications() -> dict:
        """Return platform and account notifications for the Kraken Futures account.

        Includes margin call warnings, liquidation notices, system announcements,
        and account-specific messages. Check before trading to catch active warnings.
        """
        return await client.futures_private_get("/derivatives/api/v3/notifications")

    @mcp.tool()
    async def futures_account_fee_volumes() -> dict:
        """Return the account's 30-day volume across all Futures fee schedules.

        Used to determine the current fee tier (maker/taker rates).
        Cross-reference with instrument specs to see the actual rates applying.
        """
        return await client.futures_private_get("/derivatives/api/v3/feeschedules/volumes")

    @mcp.tool()
    async def futures_account_fills(
        lastFillTime: Annotated[str | None, "ISO 8601 timestamp; return fills that occurred after this time. Omit for the most recent fills."] = None,
    ) -> dict:
        """Return recent fill (execution) history for the Kraken Futures account.

        Each fill includes symbol, side, price, size, fee, fill type
        (taker/maker), and timestamp. For streaming fills use fws_subscribe_fills.
        """
        return await client.futures_private_get("/derivatives/api/v3/fills", {
            "lastFillTime": lastFillTime,
        })
