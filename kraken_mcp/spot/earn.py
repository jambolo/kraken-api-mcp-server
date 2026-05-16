from __future__ import annotations

from typing import Annotated, Any

from ..config import Config
from ..errors import error_response
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def spot_earn_strategies(
        asset: Annotated[str | None, "Filter by asset to earn on (e.g. 'ETH', 'DOT'). Omit for all strategies."] = None,
        limit: Annotated[int | None, "Maximum results per page."] = None,
        cursor: Annotated[str | None, "Pagination cursor from a previous response."] = None,
        lock_type: Annotated[list[str] | None, "Filter by lock type(s): 'flex', 'bonded', 'timed', or 'instant'."] = None,
    ) -> dict[str, Any]:
        """Return available Kraken Earn strategies with their terms and current APY.

        Each strategy includes the asset, lock type, minimum allocation,
        current APY, payout frequency, and allocation/deallocation windows.
        Use the strategy_id from results as input for allocate/deallocate tools.
        """
        params: dict[str, Any] = {"asset": asset, "limit": limit, "cursor": cursor}
        if lock_type:
            params["lock_type"] = ",".join(lock_type)
        return await client.spot_private_post("/0/private/Earn/Strategies", params)

    @mcp.tool()
    async def spot_earn_allocations(
        asset: Annotated[str | None, "Filter allocations by asset (e.g. 'ETH'). Omit for all."] = None,
        hide_zero_allocations: Annotated[bool | None, "If true, omit strategies with a zero balance. Default false."] = None,
        converted_asset: Annotated[str | None, "Asset to express all converted amounts in (e.g. 'USD')."] = None,
        ascending: Annotated[bool | None, "Sort results ascending by strategy ID. Default false (descending)."] = None,
    ) -> dict[str, Any]:
        """Return current Kraken Earn allocations for the account.

        Each entry shows the strategy, allocated amount, payout due, and lock expiry
        if applicable. Amounts are strings; use converted_asset for a common denomination.
        """
        return await client.spot_private_post("/0/private/Earn/Allocations", {
            "asset": asset, "hide_zero_allocations": hide_zero_allocations,
            "converted_asset": converted_asset, "ascending": ascending,
        })

    @mcp.tool()
    async def spot_earn_allocate(
        strategy_id: Annotated[str, "Earn strategy ID to allocate to (from spot_earn_strategies)."],
        amount: Annotated[str, "Amount of the strategy's asset to allocate, as a string."],
    ) -> dict[str, Any]:
        """Allocate funds to a Kraken Earn strategy. Requires KRAKEN_TRADING_ENABLED=true.

        Allocation may not be immediate for bonded strategies; use
        spot_earn_allocate_status to poll until confirmed.
        Returns a pending status; check spot_earn_allocations for the updated balance.
        """
        if not cfg.trading_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRADING_ENABLED=true to enable earn allocations")
        return await client.spot_private_post("/0/private/Earn/Allocate", {
            "strategy_id": strategy_id, "amount": amount,
        })

    @mcp.tool()
    async def spot_earn_deallocate(
        strategy_id: Annotated[str, "Earn strategy ID to deallocate from (from spot_earn_strategies)."],
        amount: Annotated[str, "Amount to deallocate, as a string."],
    ) -> dict[str, Any]:
        """Deallocate funds from a Kraken Earn strategy. Requires KRAKEN_TRADING_ENABLED=true.

        Bonded strategies may have a lock period before deallocation completes.
        Use spot_earn_deallocate_status to poll until funds are returned to the Spot wallet.
        """
        if not cfg.trading_enabled:
            return error_response("disabled_by_config", "Set KRAKEN_TRADING_ENABLED=true to enable earn deallocations")
        return await client.spot_private_post("/0/private/Earn/Deallocate", {
            "strategy_id": strategy_id, "amount": amount,
        })

    @mcp.tool()
    async def spot_earn_allocate_status(
        strategy_id: Annotated[str, "Earn strategy ID to check allocation status for."],
    ) -> dict[str, Any]:
        """Return the pending allocation status for a Kraken Earn strategy.

        Call after spot_earn_allocate to determine when allocation completes.
        Returns 'pending' until the allocation is confirmed, then 'complete'.
        """
        return await client.spot_private_post("/0/private/Earn/AllocateStatus", {"strategy_id": strategy_id})

    @mcp.tool()
    async def spot_earn_deallocate_status(
        strategy_id: Annotated[str, "Earn strategy ID to check deallocation status for."],
    ) -> dict[str, Any]:
        """Return the pending deallocation status for a Kraken Earn strategy.

        Call after spot_earn_deallocate to determine when funds return to the Spot wallet.
        Returns 'pending' until complete.
        """
        return await client.spot_private_post("/0/private/Earn/DeallocateStatus", {"strategy_id": strategy_id})
