from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def futures_assign_current() -> dict[str, Any]:
        """Return the current assignment program participation for the Kraken Futures account.

        The assignment program allows the account to receive position assignments
        from liquidated counterparties in exchange for a fee. Returns active entries
        with their symbol, max quantity, and current assignment status.
        """
        return await client.futures_private_get("/derivatives/api/v3/assignmentprogram/current")

    @mcp.tool()
    async def futures_assign_add(
        symbol: Annotated[str, "Futures symbol to participate in assignment for (e.g. 'PI_XBTUSD')."],
        maxQuantity: Annotated[float, "Maximum number of contracts that can be assigned to this account per event."],
    ) -> dict[str, Any]:
        """Enroll in the assignment program for a Kraken Futures symbol.

        When a liquidation occurs, the account may receive contracts up to
        maxQuantity at the bankruptcy price in exchange for a liquidation fee credit.
        Use futures_assign_current to view existing participations.
        """
        return await client.futures_private_post("/derivatives/api/v3/assignmentprogram/add", {
            "symbol": symbol, "maxQuantity": maxQuantity,
        })

    @mcp.tool()
    async def futures_assign_delete(
        symbol: Annotated[str, "Futures symbol to remove from the assignment program (e.g. 'PI_XBTUSD')."],
    ) -> dict[str, Any]:
        """Remove the account from the assignment program for a Kraken Futures symbol.

        After deletion, the account will no longer receive contract assignments for
        this symbol. Existing positions obtained through past assignments are unaffected.
        """
        return await client.futures_private_post("/derivatives/api/v3/assignmentprogram/delete", {
            "symbol": symbol,
        })

    @mcp.tool()
    async def futures_assign_history() -> dict[str, Any]:
        """Return the assignment program event history for the Kraken Futures account.

        Each entry records an assignment event: symbol, quantity assigned,
        assignment price, fee credit received, and timestamp.
        """
        return await client.futures_private_get("/derivatives/api/v3/assignmentprogram/history")
