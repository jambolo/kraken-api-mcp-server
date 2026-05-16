from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .http_client import KrakenHttpClient
from .ws.client import FuturesWSClient
from .ws.state import WSState


def create_server() -> FastMCP:
    cfg = load_config()

    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    client = KrakenHttpClient(cfg)
    ws_state = WSState()
    ws_client = FuturesWSClient(cfg, ws_state)

    @asynccontextmanager
    async def lifespan(server: Any):
        yield
        await ws_client.stop()
        await client.close()

    mcp = FastMCP("kraken-api-mcp", lifespan=lifespan)

    # ── Spot ──────────────────────────────────────────────────────────────────
    from .spot import public as spot_public
    from .spot import trading as spot_trading
    from .spot import account as spot_account
    from .spot import funding as spot_funding
    from .spot import earn as spot_earn
    from .spot import subaccounts as spot_subaccounts
    from .spot import exports as spot_exports
    from .spot import resources as spot_resources

    spot_public.register(mcp, cfg, client)
    spot_trading.register(mcp, cfg, client)
    spot_account.register(mcp, cfg, client)
    spot_funding.register(mcp, cfg, client)
    spot_earn.register(mcp, cfg, client)
    spot_subaccounts.register(mcp, cfg, client)
    spot_exports.register(mcp, cfg, client)
    spot_resources.register(mcp, cfg, client)

    # ── Futures ───────────────────────────────────────────────────────────────
    from .futures import public as futures_public
    from .futures import trading as futures_trading
    from .futures import account as futures_account
    from .futures import prefs as futures_prefs
    from .futures import assignment as futures_assignment
    from .futures import transfers as futures_transfers
    from .futures import subaccounts as futures_subaccounts
    from .futures import history as futures_history
    from .futures import resources as futures_resources

    futures_public.register(mcp, cfg, client)
    futures_trading.register(mcp, cfg, client)
    futures_account.register(mcp, cfg, client)
    futures_prefs.register(mcp, cfg, client)
    futures_assignment.register(mcp, cfg, client)
    futures_transfers.register(mcp, cfg, client)
    futures_subaccounts.register(mcp, cfg, client)
    futures_history.register(mcp, cfg, client)
    futures_resources.register(mcp, cfg, client)

    # ── Futures WebSocket ─────────────────────────────────────────────────────
    from .ws import tools as ws_tools
    from .ws import resources as ws_resources

    ws_tools.register(mcp, cfg, ws_client, ws_state)
    ws_resources.register(mcp, cfg, ws_state)

    return mcp
