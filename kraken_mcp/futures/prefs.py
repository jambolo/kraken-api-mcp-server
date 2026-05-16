from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    def _check_trading() -> dict | None:
        if not cfg.trading_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRADING_ENABLED=true to modify Futures preferences")
        return None

    @mcp.tool()
    async def futures_prefs_pnl_get() -> dict:
        """Return the current PnL currency preferences for each Kraken Futures symbol.

        Each entry maps a symbol to the currency in which realised PnL is settled
        (e.g. 'XBT' for inverse contracts, 'USD' for linear contracts).
        """
        return await client.futures_private_get("/derivatives/api/v3/pnlpreferences")

    @mcp.tool()
    async def futures_prefs_pnl_set(
        preferences: Annotated[dict, "Mapping of Futures symbol to desired PnL settlement currency (e.g. {'PI_XBTUSD': 'XBT', 'PF_ETHUSD': 'USD'}). Only include symbols you want to change."],
    ) -> dict:
        """Set PnL currency preferences for Kraken Futures symbols. Requires KRAKEN_TRADING_ENABLED=true.

        Changes take effect for positions opened after the update.
        Use futures_prefs_pnl_get to retrieve the current settings before modifying.
        """
        if err := _check_trading():
            return err
        return await client.futures_private_put("/derivatives/api/v3/pnlpreferences", preferences)

    @mcp.tool()
    async def futures_prefs_leverage_get() -> dict:
        """Return the current maximum leverage preferences for each Kraken Futures symbol.

        Each entry maps a symbol to the maximum leverage allowed for new positions.
        The account-wide default applies to symbols not explicitly listed.
        """
        return await client.futures_private_get("/derivatives/api/v3/leveragepreferences")

    @mcp.tool()
    async def futures_prefs_leverage_set(
        preferences: Annotated[dict, "Mapping of Futures symbol to maximum leverage value (e.g. {'PI_XBTUSD': 10, 'PF_ETHUSD': 5}). Lower leverage reduces liquidation risk."],
    ) -> dict:
        """Set maximum leverage preferences for Kraken Futures symbols. Requires KRAKEN_TRADING_ENABLED=true.

        Reducing max leverage on a symbol with an active position will not
        immediately liquidate it but prevents adding leverage beyond the new limit.
        Use futures_prefs_leverage_get to check current settings before changing.
        """
        if err := _check_trading():
            return err
        return await client.futures_private_put("/derivatives/api/v3/leveragepreferences", preferences)
