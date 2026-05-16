from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    def _check_transfers() -> dict[str, Any] | None:
        if not cfg.transfers_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRANSFERS_ENABLED=true to enable Futures transfers")
        return None

    @mcp.tool()
    async def futures_transfer(
        fromAccount: Annotated[str, "Source account identifier: 'cash' for the cash/collateral account, or a margin account symbol (e.g. 'PI_XBTUSD')."],
        toAccount: Annotated[str, "Destination account identifier: 'cash' or a margin account symbol."],
        unit: Annotated[str, "Asset/currency to transfer (e.g. 'XBT', 'USD', 'USDT')."],
        amount: Annotated[float, "Amount to transfer. Must not exceed the available balance in fromAccount."],
    ) -> dict[str, Any]:
        """Transfer funds between Kraken Futures margin accounts or between a margin account and the cash account. Requires KRAKEN_TRANSFERS_ENABLED=true.

        Common use: move collateral from 'cash' into 'PI_XBTUSD' to increase
        available margin for that instrument. Transfers are immediate.
        External withdrawals are not supported; use spot_funding_wallet_transfer
        to move funds between Spot and Futures.
        """
        if err := _check_transfers():
            return err
        return await client.futures_private_post("/derivatives/api/v3/transfer", {
            "fromAccount": fromAccount, "toAccount": toAccount,
            "unit": unit, "amount": amount,
        })

    @mcp.tool()
    async def futures_transfer_subaccount(
        fromAccount: Annotated[str, "Source account identifier ('cash' or a margin account symbol)."],
        toAccount: Annotated[str, "Destination account identifier."],
        unit: Annotated[str, "Asset/currency to transfer (e.g. 'XBT', 'USD')."],
        amount: Annotated[float, "Amount to transfer."],
        subaccountUid: Annotated[str, "UID of the subaccount involved in the transfer."],
    ) -> dict[str, Any]:
        """Transfer funds between a Kraken Futures master account and a subaccount. Requires KRAKEN_TRANSFERS_ENABLED=true.

        The calling API key must belong to the master account.
        Transfers are immediate and internal — no blockchain transaction occurs.
        """
        if err := _check_transfers():
            return err
        return await client.futures_private_post("/derivatives/api/v3/transfer/subaccount", {
            "fromAccount": fromAccount, "toAccount": toAccount,
            "unit": unit, "amount": amount, "subaccountUid": subaccountUid,
        })
