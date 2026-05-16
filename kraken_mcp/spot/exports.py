from __future__ import annotations

import base64
from typing import Annotated, Any

from ..config import Config
from ..http_client import KrakenHttpClient


def register(mcp: Any, cfg: Config, client: KrakenHttpClient) -> None:

    @mcp.tool()
    async def spot_export_request(
        report: Annotated[str, "Report type: 'trades' or 'ledgers'."],
        description: Annotated[str, "Human-readable label for this export (shown in the export list)."],
        format: Annotated[str, "Output format: 'CSV' (default) or 'TSV'."] = "CSV",
        fields: Annotated[str | None, "Comma-delimited list of fields to include. Omit for all fields."] = None,
        starttm: Annotated[int | None, "Export window start as Unix timestamp. Omit for account inception."] = None,
        endtm: Annotated[int | None, "Export window end as Unix timestamp. Omit for current time."] = None,
    ) -> dict:
        """Request a data export for trades or ledgers on Kraken Spot.

        Export generation is asynchronous. Poll spot_export_status until the
        report status is 'processed', then call spot_export_retrieve with the ID.
        Returns the export report ID.
        """
        return await client.spot_private_post("/0/private/AddExport", {
            "report": report, "description": description, "format": format,
            "fields": fields, "starttm": starttm, "endtm": endtm,
        })

    @mcp.tool()
    async def spot_export_status(
        report: Annotated[str, "Report type to list: 'trades' or 'ledgers'."],
    ) -> dict:
        """Return the status of all pending and completed Spot data export requests.

        Status values: 'Queued', 'Processing', 'Processed', 'Deleted'.
        Use the 'id' field from a 'Processed' entry with spot_export_retrieve.
        """
        return await client.spot_private_post("/0/private/ExportStatus", {"report": report})

    @mcp.tool()
    async def spot_export_retrieve(
        id: Annotated[str, "Export report ID from spot_export_status (status must be 'Processed')."],
    ) -> dict:
        """Download a completed Spot data export. Returns binary content encoded as base64.

        The response includes 'content_base64' and 'content_type' fields.
        Decode with base64.b64decode() to get the raw CSV/TSV bytes.
        The export must have status 'Processed' before retrieval.
        """
        if not cfg.has_spot_auth:
            from ..errors import error_response
            return error_response("not_configured", "Spot API key/secret not configured")

        from ..auth import sign_spot_request
        data: dict[str, Any] = {"id": id}
        sign_headers = sign_spot_request("/0/private/RetrieveExport", data, cfg.spot_api_secret)  # type: ignore

        import httpx
        async with httpx.AsyncClient(timeout=cfg.http_timeout_seconds) as c:
            resp = await c.post(
                cfg.spot_base_url + "/0/private/RetrieveExport",
                data=data,
                headers={"API-Key": cfg.spot_api_key, **sign_headers},  # type: ignore
            )

        if resp.status_code != 200:
            from ..errors import error_response
            return error_response("http_error", f"HTTP {resp.status_code}")

        content_type = resp.headers.get("content-type", "application/octet-stream")
        encoded = base64.b64encode(resp.content).decode()
        return {"ok": True, "data": {"content_base64": encoded, "content_type": content_type}, "errors": []}

    @mcp.tool()
    async def spot_export_delete(
        type: Annotated[str, "'delete' to permanently remove a processed report, or 'cancel' to abort a queued/processing export."],
        id: Annotated[str, "Export report ID to delete or cancel."],
    ) -> dict:
        """Delete or cancel a Spot data export report.

        Use 'cancel' to abort a queued or in-progress export, or 'delete' to
        remove a processed report and free server-side storage.
        """
        return await client.spot_private_post("/0/private/RemoveExport", {"type": type, "id": id})

    @mcp.tool()
    async def spot_ws_get_token() -> dict:
        """Return a short-lived WebSocket authentication token for Kraken Spot WS v2.

        The token is valid for 15 minutes. Pass it as 'token' when authenticating
        to the Spot WebSocket API. Note: Spot WS streaming is outside this server's
        scope; this tool is provided for downstream clients that connect independently.
        """
        return await client.spot_private_post("/0/private/GetWebSocketsToken")
