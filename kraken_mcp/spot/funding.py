from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def spot_funding_deposit_methods(
        asset: Annotated[str, "Asset to get deposit methods for (e.g. 'XBT', 'ETH', 'USD')."],
    ) -> dict[str, Any]:
        """Return available deposit methods for a Spot asset.

        Each method includes its name, minimum deposit amount, fee structure,
        whether an address is required, and setup instructions if applicable.
        Call this before spot_funding_deposit_addresses to know which method name to use.
        """
        return await client.spot_private_post("/0/private/DepositMethods", {"asset": asset})

    @mcp.tool()
    async def spot_funding_deposit_addresses(
        asset: Annotated[str, "Asset to get deposit addresses for (e.g. 'XBT')."],
        method: Annotated[str, "Deposit method name as returned by spot_funding_deposit_methods (e.g. 'Bitcoin')."],
        new: Annotated[bool | None, "If true, generate a fresh deposit address even if one already exists. Default false."] = None,
        amount: Annotated[str | None, "For methods that require a specific amount (e.g. fiat rails), the exact deposit amount as a string."] = None,
    ) -> dict[str, Any]:
        """Return deposit addresses for a Spot asset and deposit method.

        Re-uses an existing address unless new=true is requested.
        Some addresses include an expiry time; always re-check before sharing.
        """
        return await client.spot_private_post("/0/private/DepositAddresses", {
            "asset": asset, "method": method, "new": new, "amount": amount,
        })

    @mcp.tool()
    async def spot_funding_deposit_status(
        asset: Annotated[str | None, "Filter by asset (e.g. 'XBT'). Omit for all assets."] = None,
        method: Annotated[str | None, "Filter by deposit method name."] = None,
        start: Annotated[str | None, "Start of time range as Unix timestamp."] = None,
        end: Annotated[str | None, "End of time range as Unix timestamp."] = None,
        cursor: Annotated[str | None, "Pagination cursor returned in the previous response."] = None,
        limit: Annotated[int | None, "Maximum number of records per page (default 25, max 50)."] = None,
    ) -> dict[str, Any]:
        """Return recent deposit history for the Spot account with pagination.

        Each entry includes the asset, method, network transaction ID, amount,
        fee, confirmations, status, and timestamps.
        """
        return await client.spot_private_post("/0/private/DepositStatus", {
            "asset": asset, "method": method, "start": start, "end": end,
            "cursor": cursor, "limit": limit,
        })

    @mcp.tool()
    async def spot_funding_wallet_transfer(
        asset: Annotated[str, "Asset to transfer (e.g. 'XBT', 'USD')."],
        from_: Annotated[str, "Source wallet: 'Spot Wallet' or 'Futures Wallet'."],
        to: Annotated[str, "Destination wallet: 'Spot Wallet' or 'Futures Wallet'."],
        amount: Annotated[str, "Amount to transfer as a string to preserve precision."],
    ) -> dict[str, Any]:
        """Transfer funds between the Kraken Spot and Futures wallets (internal only). Requires KRAKEN_TRANSFERS_ENABLED=true.

        This is an on-platform transfer — no blockchain transaction occurs.
        Funds are available in the destination wallet immediately.
        External withdrawals are intentionally not supported by this server.
        """
        if not cfg.transfers_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRANSFERS_ENABLED=true to enable transfers")
        return await client.spot_private_post("/0/private/WalletTransfer", {
            "asset": asset, "from": from_, "to": to, "amount": amount,
        })
