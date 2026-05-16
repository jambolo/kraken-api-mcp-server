from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def futures_subaccount_list() -> dict[str, Any]:
        """Return all Kraken Futures subaccounts associated with the master account.

        Each entry includes the subaccount UID, name, and whether trading is enabled.
        The calling API key must belong to the master account.
        """
        return await client.futures_private_get("/derivatives/api/v3/subaccounts")

    @mcp.tool()
    async def futures_subaccount_trading_get(
        uid: Annotated[str, "Subaccount UID (from futures_subaccount_list)."],
    ) -> dict[str, Any]:
        """Return whether trading is currently enabled for a Kraken Futures subaccount.

        Returns a boolean tradingEnabled field for the specified subaccount UID.
        """
        return await client.futures_private_get(f"/derivatives/api/v3/subaccount/{uid}/trading-enabled")

    @mcp.tool()
    async def futures_subaccount_trading_set(
        uid: Annotated[str, "Subaccount UID (from futures_subaccount_list)."],
        enabled: Annotated[bool, "True to enable trading for this subaccount, false to disable."],
    ) -> dict[str, Any]:
        """Enable or disable trading for a Kraken Futures subaccount. Requires KRAKEN_TRADING_ENABLED=true.

        Disabling trading prevents the subaccount from placing new orders but does
        not cancel existing open orders. Use futures_trade_cancel_all_orders on
        the subaccount's API key first if a clean halt is needed.
        """
        if not cfg.trading_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRADING_ENABLED=true to modify subaccount trading")
        return await client.futures_private_put(
            f"/derivatives/api/v3/subaccount/{uid}/trading-enabled",
            {"tradingEnabled": enabled},
        )
