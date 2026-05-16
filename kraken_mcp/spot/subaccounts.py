from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def spot_subaccount_create(
        username: Annotated[str, "Desired username for the new subaccount (must be unique within the master account)."],
        email: Annotated[str, "Email address for the new subaccount. Used for login and notifications."],
    ) -> dict[str, Any]:
        """Create a new Spot subaccount under the current master account (institutional accounts only).

        Subaccounts share the master account's fee tier but have independent balances
        and API keys. Returns the new account's UID on success.
        This endpoint is only available to institutional/prime clients.
        """
        return await client.spot_private_post("/0/private/CreateSubaccount", {
            "username": username, "email": email,
        })

    @mcp.tool()
    async def spot_subaccount_transfer(
        asset: Annotated[str, "Asset to transfer (e.g. 'XBT', 'USD')."],
        amount: Annotated[str, "Amount to transfer as a string."],
        from_: Annotated[str, "UID of the source account (master or subaccount)."],
        to: Annotated[str, "UID of the destination account (master or subaccount)."],
    ) -> dict[str, Any]:
        """Transfer funds between the master Spot account and a subaccount. Requires KRAKEN_TRANSFERS_ENABLED=true.

        Transfers are immediate and internal (no blockchain transaction).
        The calling API key must belong to the master account.
        """
        if not cfg.transfers_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRANSFERS_ENABLED=true to enable transfers")
        return await client.spot_private_post("/0/private/AccountTransfer", {
            "asset": asset, "amount": amount, "from": from_, "to": to,
        })
