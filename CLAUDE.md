# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable + dev deps)
uv sync --extra dev

# Run server (stdio transport)
uv run python -m kraken_mcp

# Tests
uv run pytest tests/
uv run pytest tests/test_auth.py::test_spot_sign_produces_api_sign_header   # single test
uv run pytest tests/ -x -q   # fail-fast, quiet
```

No build step. No linter configured yet.

## Architecture

### Registration pattern

`server.py:create_server()` is the only entry point. It constructs `Config`, `KrakenHttpClient`, `FuturesWSClient`, and `WSState`, then calls `module.register(mcp, cfg, client)` for every sub-module. Tools are closures that capture `cfg` and `client` — there are no global singletons and no dependency injection framework.

```
server.py → spot/{public,trading,account,funding,earn,subaccounts,exports,resources}.py
          → futures/{public,trading,account,prefs,assignment,transfers,subaccounts,history,resources}.py
          → ws/{tools,resources}.py
```

### Response contract

Every tool returns the same envelope (never raises to the LLM):

```python
{"ok": bool, "data": ..., "errors": [{"code": str, "message": str}], "raw_status": int, "rate_limit": {...}}
```

`errors.py` normalizes both Spot (`{error:[], result:{}}`) and Futures (`{result:"success"|"error"}`) shapes into this form. `error_response()` constructs a local refusal with the same shape (used for gate checks before any HTTP call).

### Safety gates

Two `cfg` booleans checked inline at the top of each mutating tool:

- `cfg.trading_enabled` (`KRAKEN_TRADING_ENABLED=true`) — order placement/edit/cancel, earn allocate/deallocate, leverage/pnl prefs set, subaccount trading set
- `cfg.transfers_enabled` (`KRAKEN_TRANSFERS_ENABLED=true`) — wallet transfer, futures transfer, subaccount transfer

Cancel-all tools additionally require a `confirm: bool = False` argument; without it they return `error_response("confirmation_required", ...)` before hitting Kraken.

### Auth

`auth.py` is pure functions — no state, no I/O. `sign_spot_request` mutates `data` in-place to inject `nonce`. `sign_futures_request` returns `(nonce, headers_dict)`; the caller fills in `APIKey`. WS challenge signing is separate (`sign_futures_ws_challenge`).

### Rate limiting

`SpotRateLimiter` — async token bucket, tier-aware (starter/intermediate/pro), decays at `_SPOT_TIERS[tier]` per second, with a per-endpoint cost table in `_SPOT_COSTS`. Order endpoints (AddOrder, CancelOrder, etc.) have cost 0 — they bypass the counter per Kraken's docs.

`FuturesRateLimiter` — 500-unit budget per 10-second rolling window.

Both raise `TimeoutError` if the wait would exceed `KRAKEN_HTTP_TIMEOUT_SECONDS`.

### WebSocket

`ws/client.py:FuturesWSClient` — lazy-started (`start()` called on first subscribe tool). Persistent asyncio task with exponential-backoff reconnect. Private feeds trigger a challenge handshake (`_ensure_challenge()`), which is cached for the WS session lifetime. Subscriptions are tracked in `_pending_subs` and replayed on reconnect.

`ws/state.py:WSState` — two cache strategies:
- **Last-message-wins**: `ticker`, `ticker_lite`, `open_orders`, `open_positions`, `balances` — keyed by `(feed, product_id)`.
- **Ring buffer** (size 1000): `trade`, `fills`, `account_log`, `deposits_withdrawals`, `notifications_auth`.
- **L2 book**: delta-applied bid/ask dicts per symbol; `snapshot()` returns sorted levels.

`fws_drain` clears the ring buffer for the requested feed/product. WS resources return `{"status":"not-subscribed"}` until the matching subscribe tool has been called.

### HTTP client

`KrakenHttpClient` wraps `httpx.AsyncClient` (HTTP/2). `_retry()` retries up to 3 times on `{429, 500, 502, 503, 504}` with linear back-off. Client is lazily created and reused across calls.
