# Kraken MCP Server -- Design

**Status:** Design v1
**Target runtime:** Python 3.11+, `mcp` SDK, stdio transport
**Scope:** Kraken Spot REST (public + private), Futures REST (public + private), Futures WebSocket (public + private)
**Trading authority:** Full trading (place, edit, cancel orders; internal wallet transfers). **External withdrawals excluded.**

---

## 1. Goals & Non-Goals

### Goals

- 1:1 tool-per-endpoint mapping for auditability and per-tool permissioning.
- Cover all Spot REST market-data and trading-grade endpoints plus Futures REST/WS.
- Expose frequently-polled reference data (assets, pairs, instruments, system status) as MCP **resources** so LLMs can read them without burning a tool call.
- Stream WebSocket state into a server-side cache; expose cache via tools (snapshot) and resources (latest value).
- Provide a `validate`/dry-run path for every order-mutating tool.

### Non-Goals

- No external withdrawal endpoints (`/private/Withdraw*`, futures `/withdrawal`).
- No Spot WS v2 (out of scope per requirements; only Futures WS).
- No NFT API.
- Not a trading framework -- no strategies, no order-routing logic, no PnL accounting beyond what Kraken returns.

---

## 2. Architecture

```text
kraken-mcp/
|--- pyproject.toml
|--- kraken_mcp/
| |--- __main__.py              # `python -m kraken_mcp` stdio entrypoint
| |--- server.py                # FastMCP instance, tool/resource registration
| |--- config.py                # env-var loading, validation
| |--- auth.py                  # nonce, API-Sign (spot), Authent (futures)
| |--- http_client.py           # httpx.AsyncClient w/ retry, rate-limit budget
| |--- rate_limit.py            # token-bucket per Kraken's published budgets
| |--- errors.py                # KrakenError --> MCP error mapping
| |--- spot/
| | |--- public.py            # market data tools
| | |--- trading.py           # order tools
| | |--- account.py           # balances, orders, ledgers, trades
| | |--- funding.py           # deposit-only + wallet transfer
| | |--- earn.py              # staking/earn tools
| | |--- subaccounts.py       # institutional tools
| | |--- exports.py           # data export tools
| | `-- resources.py         # asset/pair/status resources
| |--- futures/
| | |--- public.py            # tickers, instruments, orderbook, history, charts
| | |--- trading.py           # send/edit/cancel/batch
| | |--- account.py           # accounts, positions, margin, fees
| | |--- prefs.py             # pnl/leverage preferences
| | |--- assignment.py        # assignment-program tools
| | |--- transfers.py         # internal transfers, subaccount transfers
| | |--- subaccounts.py
| | |--- history.py           # /api/history/v3
| | `-- resources.py         # instruments, status resources
| |--- ws/
| | |--- client.py            # asyncio WS client w/ challenge handshake
| | |--- state.py             # last-message cache keyed by (feed, symbol)
| | |--- tools.py             # subscribe/unsubscribe/snapshot/drain tools
| | `-- resources.py         # `kraken-futures-ws://...` resources
| `-- schemas/                 # Pydantic models per endpoint
`-- tests/
```

### Key dependencies

- `mcp` (official Python SDK, `FastMCP`)
- `httpx[http2]` -- async REST
- `websockets` -- Futures WS client
- `pydantic` v2 -- request/response models, schema generation
- `anyio` -- concurrency primitives (matches MCP SDK)

### Process model

Single async process. Background tasks:

- One persistent Futures WS connection (lazy-started on first subscribe).
- Rate-limit token refill timer.
- Optional REST-poll task for the staleness watchdog on cached resources.

---

## 3. Configuration

All settings via environment variables; no config file.

| Variable | Required | Purpose |
| --- | --- | --- |
| `KRAKEN_SPOT_API_KEY` | optional | Spot REST private auth. Public-only mode if unset. |
| `KRAKEN_SPOT_API_SECRET` | with key | Base64 Spot secret. |
| `KRAKEN_FUTURES_API_KEY` | optional | Futures auth. |
| `KRAKEN_FUTURES_API_SECRET` | with key | Base64 Futures secret. |
| `KRAKEN_FUTURES_ENV` | optional | `live` (default) or `demo` (uses `demo-futures.kraken.com`). |
| `KRAKEN_TRADING_ENABLED` | optional | `false` (default) --> trading tools refuse with explicit message. Must be `true` to place/edit/cancel orders. Defense-in-depth: tool exists, refuses without env. |
| `KRAKEN_TRANSFERS_ENABLED` | optional | `false` (default) --> internal-transfer tools refuse. |
| `KRAKEN_SPOT_RATE_LIMIT_TIER` | optional | `starter`/`intermediate`/`pro` -- sets request budget. Default `intermediate`. |
| `KRAKEN_HTTP_TIMEOUT_SECONDS` | optional | Default 30. |
| `KRAKEN_LOG_LEVEL` | optional | `INFO`/`DEBUG`. |

Startup validation: if any private tool is registered and the corresponding key/secret pair is incomplete, log a warning and have the tool emit a `not-configured` error at call time (don't crash the server).

---

## 4. Authentication

### Spot REST private

- Per Kraken: `nonce = int(time.time() * 1000)`, monotonically increasing.
- `API-Sign = base64( HMAC_SHA512( base64_decode(secret), uri_path + sha256(nonce + post_data) ) )`
- Implemented once in `auth.sign_spot_request(path, body)`. Returns headers dict.

### Futures REST private

- `Nonce = strictly increasing int` (use spot nonce strategy).
- `Authent = base64( HMAC_SHA512( base64_decode(secret), sha256(postData + nonce + endpointPath) ) )`
- `endpointPath` is the path after the host **excluding** `/derivatives` prefix (per Kraken's signing example).

### Futures WS challenge handshake

1. Send `{event:"challenge", api_key}`.
2. Receive `{event:"challenge", message:<uuid>}`.
3. `original_challenge = uuid`; `signed_challenge = base64( HMAC_SHA512( base64_decode(secret), sha256(uuid) ) )`.
4. Include both fields on every private `subscribe`/`unsubscribe`.

Cache the signed challenge per connection (it's valid for the lifetime of the WS session).

---

## 5. Resources

Resources are read-only URIs with stable shape -- ideal for reference data the LLM needs to consult before every tool call.

| URI | Mime | Source | Refresh |
| --- | --- | --- | --- |
| `kraken-spot://system-status` | application/json | `GET /public/SystemStatus` | 60 s TTL |
| `kraken-spot://assets` | application/json | `GET /public/Assets` | 1 h TTL |
| `kraken-spot://asset-pairs` | application/json | `GET /public/AssetPairs` | 1 h TTL |
| `kraken-spot://asset-pairs/{pair}` | application/json | filtered slice | derived |
| `kraken-spot://ticker/{pair}` | application/json | `GET /public/Ticker` | 5 s TTL |
| `kraken-futures://instruments` | application/json | `GET /derivatives/api/v3/instruments` | 5 min TTL |
| `kraken-futures://instruments/trading` | application/json | `_/instruments/trading` | 5 min TTL |
| `kraken-futures://instrument-status` | application/json | `_/instruments/status` | 30 s TTL |
| `kraken-futures://tickers` | application/json | `_/tickers` | 5 s TTL |
| `kraken-futures-ws://book/{symbol}` | application/json | WS `book` cached snapshot | live (cache) |
| `kraken-futures-ws://ticker/{symbol}` | application/json | WS `ticker` cached snapshot | live (cache) |
| `kraken-futures-ws://open-orders` | application/json | WS `open_orders` cache | live (cache) |
| `kraken-futures-ws://open-positions` | application/json | WS `open_positions` cache | live (cache) |
| `kraken-futures-ws://balances` | application/json | WS `balances` cache | live (cache) |
| `kraken-futures-ws://fills` | application/json | WS `fills` ring buffer (last 200) | live (cache) |

WS resources return `{status:"not-subscribed"}` until the matching subscribe-tool is called. This is intentional: surfacing the resource list signals what's *available*, while the tool is the explicit "start streaming" action.

---

## 6. Tools

Naming: `{surface}_{group}_{action}`, lowercase snake_case. Surfaces: `spot`, `futures`, `fws` (futures WS).

Every tool's input schema is a Pydantic model; output is the parsed Kraken response with errors normalised. All trading tools accept `validate: bool = False` where Kraken supports it (Spot AddOrder/AmendOrder/EditOrder/AddOrderBatch); for Futures, validation is exposed via a separate `_dry_run` flag that calls `/initialmargin` + max-order-size first.

### 6.1 Spot -- Market Data (public, no key)

| Tool | Endpoint | Notes |
| --- | --- | --- |
| `spot_public_server_time` | `GET /0/public/Time` | |
| `spot_public_system_status` | `GET /0/public/SystemStatus` | |
| `spot_public_assets` | `GET /0/public/Assets` | Optional `asset`, `aclass`. |
| `spot_public_asset_pairs` | `GET /0/public/AssetPairs` | Optional `pair`, `info`, `country_code`. |
| `spot_public_ticker` | `GET /0/public/Ticker` | `pair` (str or list). |
| `spot_public_ohlc` | `GET /0/public/OHLC` | `pair`, `interval` (1/5/15/30/60/240/1440/10080/21600), `since`. |
| `spot_public_orderbook` | `GET /0/public/Depth` | `pair`, `count` (<=500). |
| `spot_public_recent_trades` | `GET /0/public/Trades` | `pair`, `since`, `count`. |
| `spot_public_recent_spreads` | `GET /0/public/Spread` | `pair`, `since`. |

### 6.2 Spot -- Trading (private, gated by `KRAKEN_TRADING_ENABLED=true`)

| Tool | Endpoint | Notes |
| --- | --- | --- |
| `spot_trade_add_order` | `POST /0/private/AddOrder` | Full param set incl. `close[...]`, `validate`. |
| `spot_trade_add_order_batch` | `POST /0/private/AddOrderBatch` | <=15 orders per pair. |
| `spot_trade_amend_order` | `POST /0/private/AmendOrder` | In-place modify. |
| `spot_trade_edit_order` | `POST /0/private/EditOrder` | Cancel-and-replace; legacy. |
| `spot_trade_cancel_order` | `POST /0/private/CancelOrder` | |
| `spot_trade_cancel_all_orders` | `POST /0/private/CancelAllOrders` | **Confirmation flag required** (`confirm: bool = False` -- refuses without). |
| `spot_trade_cancel_all_orders_after` | `POST /0/private/CancelAllOrdersAfter` | Dead-man's switch. |
| `spot_trade_cancel_order_batch` | `POST /0/private/CancelOrderBatch` | <=50 IDs. |

### 6.3 Spot -- Account & History (private, read-only)

| Tool | Endpoint |
| --- | --- |
| `spot_account_balance` | `POST /0/private/Balance` |
| `spot_account_balance_ex` | `POST /0/private/BalanceEx` |
| `spot_account_trade_balance` | `POST /0/private/TradeBalance` |
| `spot_account_open_orders` | `POST /0/private/OpenOrders` |
| `spot_account_closed_orders` | `POST /0/private/ClosedOrders` |
| `spot_account_query_orders` | `POST /0/private/QueryOrders` |
| `spot_account_order_amends` | `POST /0/private/OrderAmends` |
| `spot_account_trades_history` | `POST /0/private/TradesHistory` |
| `spot_account_query_trades` | `POST /0/private/QueryTrades` |
| `spot_account_open_positions` | `POST /0/private/OpenPositions` |
| `spot_account_ledgers` | `POST /0/private/Ledgers` |
| `spot_account_query_ledgers` | `POST /0/private/QueryLedgers` |
| `spot_account_trade_volume` | `POST /0/private/TradeVolume` |

### 6.4 Spot -- Funding (deposit-only + internal transfers, withdrawals excluded)

| Tool | Endpoint | Notes |
| --- | --- | --- |
| `spot_funding_deposit_methods` | `POST /0/private/DepositMethods` | |
| `spot_funding_deposit_addresses` | `POST /0/private/DepositAddresses` | |
| `spot_funding_deposit_status` | `POST /0/private/DepositStatus` | |
| `spot_funding_wallet_transfer` | `POST /0/private/WalletTransfer` | Spot<-->Futures internal. Gated by `KRAKEN_TRANSFERS_ENABLED=true`. |

**Intentionally omitted:** `WithdrawMethods`, `WithdrawAddresses`, `WithdrawInfo`, `Withdraw`, `WithdrawStatus`, `WithdrawCancel`.

### 6.5 Spot -- Earn / Staking (private)

| Tool | Endpoint |
| --- | --- |
| `spot_earn_strategies` | `POST /0/private/Earn/Strategies` |
| `spot_earn_allocations` | `POST /0/private/Earn/Allocations` |
| `spot_earn_allocate` | `POST /0/private/Earn/Allocate` |
| `spot_earn_deallocate` | `POST /0/private/Earn/Deallocate` |
| `spot_earn_allocate_status` | `POST /0/private/Earn/AllocateStatus` |
| `spot_earn_deallocate_status` | `POST /0/private/Earn/DeallocateStatus` |

`allocate`/`deallocate` gated by `KRAKEN_TRADING_ENABLED`.

### 6.6 Spot -- Subaccounts (institutional)

| Tool | Endpoint |
| --- | --- |
| `spot_subaccount_create` | `POST /0/private/CreateSubaccount` |
| `spot_subaccount_transfer` | `POST /0/private/AccountTransfer` (gated by `KRAKEN_TRANSFERS_ENABLED`) |

### 6.7 Spot -- Data Exports

| Tool | Endpoint | Notes |
| --- | --- | --- |
| `spot_export_request` | `POST /0/private/AddExport` | |
| `spot_export_status` | `POST /0/private/ExportStatus` | |
| `spot_export_retrieve` | `POST /0/private/RetrieveExport` | Returns binary; surfaced as base64 in MCP response with `content_type` field. |
| `spot_export_delete` | `POST /0/private/RemoveExport` | |

### 6.8 Spot -- WS Token

| Tool | Endpoint | Notes |
| --- | --- | --- |
| `spot_ws_get_token` | `POST /0/private/GetWebSocketsToken` | Provided for completeness; Spot WS v2 itself is out of scope. |

### 6.9 Futures -- Market Data (public)

| Tool | Endpoint |
| --- | --- |
| `futures_public_tickers` | `GET /derivatives/api/v3/tickers` |
| `futures_public_ticker` | `GET /derivatives/api/v3/tickers/{symbol}` |
| `futures_public_instruments` | `GET /derivatives/api/v3/instruments` |
| `futures_public_instruments_trading` | `GET /derivatives/api/v3/instruments/trading` |
| `futures_public_instrument_status_list` | `GET /derivatives/api/v3/instruments/status` |
| `futures_public_instrument_status` | `GET /derivatives/api/v3/instruments/{symbol}/status` |
| `futures_public_orderbook` | `GET /derivatives/api/v3/orderbook` |
| `futures_public_history` | `GET /derivatives/api/v3/history` |
| `futures_public_funding_rates` | `GET /derivatives/api/v3/historical-funding-rates` |

### 6.10 Futures -- Charts (public)

| Tool | Endpoint |
| --- | --- |
| `futures_chart_tick_types` | `GET /api/charts/v1/` |
| `futures_chart_symbols` | `GET /api/charts/v1/{tick_type}` |
| `futures_chart_resolutions` | `GET /api/charts/v1/{tick_type}/{symbol}` |
| `futures_chart_candles` | `GET /api/charts/v1/{tick_type}/{symbol}/{resolution}` |
| `futures_chart_liquidity_pool` | `GET /api/charts/v1/analytics/liquidity-pool` |
| `futures_chart_analytics` | `GET /api/charts/v1/analytics/{symbol}/{analytics_type}` |

### 6.11 Futures -- Trading (private, gated)

| Tool | Endpoint |
| --- | --- |
| `futures_trade_send_order` | `POST /derivatives/api/v3/sendorder` |
| `futures_trade_edit_order` | `POST /derivatives/api/v3/editorder` |
| `futures_trade_cancel_order` | `POST /derivatives/api/v3/cancelorder` |
| `futures_trade_cancel_all_orders` | `POST /derivatives/api/v3/cancelallorders` (per-symbol optional). **Confirmation required.** |
| `futures_trade_cancel_all_after` | `POST /derivatives/api/v3/cancelallordersafter` |
| `futures_trade_batch_order` | `POST /derivatives/api/v3/batchorder` |
| `futures_trade_open_orders` | `GET /derivatives/api/v3/openorders` |
| `futures_trade_orders_status` | `POST /derivatives/api/v3/orders/status` |

### 6.12 Futures -- Account (private read)

| Tool | Endpoint |
| --- | --- |
| `futures_account_get` | `GET /derivatives/api/v3/accounts` |
| `futures_account_open_positions` | `GET /derivatives/api/v3/openpositions` |
| `futures_account_unwind_queue` | `GET /derivatives/api/v3/unwindqueue` |
| `futures_account_initial_margin` | `GET /derivatives/api/v3/initialmargin` |
| `futures_account_max_order_size` | `GET /derivatives/api/v3/initialmargin/maxordersize` |
| `futures_account_notifications` | `GET /derivatives/api/v3/notifications` |
| `futures_account_fee_volumes` | `GET /derivatives/api/v3/feeschedules/volumes` |
| `futures_account_fills` | `GET /derivatives/api/v3/fills` |

### 6.13 Futures -- Preferences (private mutating)

| Tool | Endpoint |
| --- | --- |
| `futures_prefs_pnl_get` | `GET /derivatives/api/v3/pnlpreferences` |
| `futures_prefs_pnl_set` | `PUT /derivatives/api/v3/pnlpreferences` |
| `futures_prefs_leverage_get` | `GET /derivatives/api/v3/leveragepreferences` |
| `futures_prefs_leverage_set` | `PUT /derivatives/api/v3/leveragepreferences` |

`*_set` gated by `KRAKEN_TRADING_ENABLED` (they meaningfully change risk).

### 6.14 Futures -- Assignment Program

| Tool | Endpoint |
| --- | --- |
| `futures_assign_current` | `GET /derivatives/api/v3/assignmentprogram/current` |
| `futures_assign_add` | `POST /derivatives/api/v3/assignmentprogram/add` |
| `futures_assign_delete` | `POST /derivatives/api/v3/assignmentprogram/delete` |
| `futures_assign_history` | `GET /derivatives/api/v3/assignmentprogram/history` |

### 6.15 Futures -- Internal Transfers (withdrawals excluded)

| Tool | Endpoint |
| --- | --- |
| `futures_transfer` | `POST /derivatives/api/v3/transfer` (between margin accts of same collateral or margin<-->cash). Gated by `KRAKEN_TRANSFERS_ENABLED`. |
| `futures_transfer_subaccount` | `POST /derivatives/api/v3/transfer/subaccount`. Gated by `KRAKEN_TRANSFERS_ENABLED`. |

**Intentionally omitted:** `POST /derivatives/api/v3/withdrawal`.

### 6.16 Futures -- Subaccounts

| Tool | Endpoint |
| --- | --- |
| `futures_subaccount_list` | `GET /derivatives/api/v3/subaccounts` |
| `futures_subaccount_trading_get` | `GET /derivatives/api/v3/subaccount/{uid}/trading-enabled` |
| `futures_subaccount_trading_set` | `PUT /derivatives/api/v3/subaccount/{uid}/trading-enabled` (gated by `KRAKEN_TRADING_ENABLED`) |

### 6.17 Futures -- History v3

| Tool | Endpoint |
| --- | --- |
| `futures_history_executions` | `GET /api/history/v3/executions` |
| `futures_history_orders` | `GET /api/history/v3/orders` |
| `futures_history_triggers` | `GET /api/history/v3/triggers` |
| `futures_history_public_executions` | `GET /api/history/v3/market/{tradeable}/executions` |
| `futures_history_public_orders` | `GET /api/history/v3/market/{tradeable}/orders` |
| `futures_history_public_price` | `GET /api/history/v3/market/{tradeable}/price` |

### 6.18 Futures WebSocket (subscribe + cache + drain pattern)

WS feeds are streaming, but MCP tools are request/response. Three-part pattern:

1. **Subscribe tool** -- opens (or reuses) the persistent WS connection, sends `subscribe`, returns `{status:"subscribed", feed, product_ids?}`. Sets up an in-process consumer that updates the cache.
2. **Snapshot tool / resource** -- returns the latest cached state immediately.
3. **Drain tool** -- returns all messages received since the last `drain` call for the given (feed, product) and clears the buffer. Useful for backtest-style "show me everything that happened in the last 30 s" flows.

| Tool | Op | Notes |
| --- | --- | --- |
| `fws_subscribe_book` | subscribe public | `product_ids: list[str]` |
| `fws_subscribe_ticker` | subscribe public | |
| `fws_subscribe_ticker_lite` | subscribe public | |
| `fws_subscribe_trade` | subscribe public | |
| `fws_subscribe_heartbeat` | subscribe public | |
| `fws_subscribe_open_orders` | subscribe private | Triggers challenge handshake on first private sub. |
| `fws_subscribe_open_orders_verbose` | subscribe private | |
| `fws_subscribe_fills` | subscribe private | optional `product_ids` |
| `fws_subscribe_open_positions` | subscribe private | |
| `fws_subscribe_balances` | subscribe private | |
| `fws_subscribe_account_log` | subscribe private | |
| `fws_subscribe_notifications` | subscribe private | feed `notifications_auth` |
| `fws_subscribe_deposits_withdrawals` | subscribe private | |
| `fws_unsubscribe` | unsubscribe | `feed`, `product_ids?` |
| `fws_list_subscriptions` | introspection | Current subs + queue depths. |
| `fws_snapshot` | read cache | `feed`, `product_id?` --> latest cached payload. |
| `fws_drain` | drain buffer | `feed`, `product_id?`, `max: int = 1000` --> messages, clears buffer. |
| `fws_status` | introspection | Connection state, last challenge time, reconnect count, last heartbeat. |
| `fws_close` | teardown | Disconnect; cache retained until process exit. |

#### Cache semantics

- `book`: per-symbol L2 bid/ask maps maintained by applying deltas to the snapshot; resource returns a normalised top-N view (`depth: int = 10`).
- `ticker`/`ticker_lite`/`open_orders`/`open_positions`/`balances`: last-message wins.
- `trade`/`fills`/`account_log`/`deposits_withdrawals`/`notifications_auth`: ring buffer (size 1000, configurable).

---

## 7. Safety & Confirmation

| Class | Rule |
| --- | --- |
| Read-only public | No env gate. |
| Read-only private | Requires keys; no confirm flag. |
| Order place / edit / amend | Requires `KRAKEN_TRADING_ENABLED=true`. Schema exposes `validate` for Spot dry-runs. |
| Cancel single order | Requires `KRAKEN_TRADING_ENABLED=true`. No confirm flag (per-order cancel is low-risk). |
| Cancel **all** orders | Requires `KRAKEN_TRADING_ENABLED=true` **and** `confirm=true` argument. Without confirm, the tool returns an explanatory error instead of calling Kraken. |
| Internal transfer (Spot<-->Futures, master<-->sub) | Requires `KRAKEN_TRANSFERS_ENABLED=true`. |
| Leverage / PnL prefs change | Requires `KRAKEN_TRADING_ENABLED=true`. |
| External withdrawal | **Not implemented.** |

The MCP server also surfaces a `kraken-safety://config` resource that lists which gates are currently open -- so the host can show the user "trading: enabled, transfers: disabled" before authorising a tool call.

---

## 8. Error Model

Normalise every response. Spot returns `{error:[], result:{...}}`; Futures returns `{result:"success"|"error", error?, errors?}`. Map both to:

```python
{
  "ok": bool,
  "data": <result>,
  "errors": [{"code": str, "message": str}],   # empty when ok
  "raw_status": int,
  "rate_limit": {"remaining": int, "reset_in_s": float}
}
```

Map well-known error strings to MCP error responses with stable codes:

| Kraken error | MCP code |
| --- | --- |
| `EAPI:Invalid key` / `EAPI:Invalid signature` | `auth_failed` |
| `EOrder:Insufficient funds` | `insufficient_funds` |
| `EGeneral:Permission denied` | `permission_denied` |
| `EAPI:Rate limit exceeded` / HTTP 429 | `rate_limited` (with retry-after) |
| `EService:Unavailable` / 5xx | `upstream_unavailable` |
| Futures `apiLimitExceeded` | `rate_limited` |
| Local gate refusal (`KRAKEN_TRADING_ENABLED=false`) | `disabled_by_config` |

---

## 9. Rate Limiting

Two independent token buckets, refilled by a background timer:

- **Spot:** per-tier max counter (15/20/20) with per-endpoint cost (Kraken's `counter cost` table). Implemented as a single bucket scaled by tier; private trading endpoints (`AddOrder`/`CancelOrder` etc.) carry per-endpoint multipliers documented in `rate_limit.py`.
- **Futures:** 500 budget per rolling 10 s for `/derivatives/*`; public endpoints free; history endpoints have their own cost (1 per request).

When a bucket would go negative, the tool waits up to `KRAKEN_HTTP_TIMEOUT_SECONDS` before erroring with `rate_limited`. The wait is reported in the result so the LLM can pace itself.

---

## 10. Schema patterns

- All tool inputs validated by Pydantic v2 -- `model_config = ConfigDict(extra='forbid')` to reject typos.
- Symbol params accept either a single string or a list; normalised at the edge.
- Timestamps: tool inputs accept ISO-8601 or epoch-seconds; outputs pass through Kraken's native format with an additional `_iso` field for convenience.
- Decimal fields kept as strings in transit; tool docstrings note this to discourage float rounding.

---

## 11. Open questions / decisions for the next pass

1. Should `fws_drain` blocking? Default proposal: non-blocking, return whatever is currently buffered. Add `wait_ms: int = 0` to optionally block.
2. Order placement: expose `cl_ord_id` auto-generation (uuid7) or require caller to supply? Proposal: optional; auto-generate when omitted and surface in response.
3. `validate` flag default for Spot trading tools: `false` (matches Kraken). Proposal: leave at `false` so the LLM must explicitly pass `validate=true` for dry-runs; never force.
4. Should we ship a `kraken-mcp doctor` CLI subcommand to verify keys/permissions before connecting? Proposal: yes -- `python -m kraken_mcp doctor`.

---

## 12. Prompts

MCP prompts = parameterized templates exposed by the server. Each is a named slash-command-style entry the host UI surfaces to the user; arguments fill placeholders before the prompt is sent to the LLM. Goal: package recurring multi-tool workflows so the user doesn't have to phrase them.

Naming: same `{surface}_{group}_{action}` convention. All marked **read-only** unless noted; "trading" prompts will only succeed when `KRAKEN_TRADING_ENABLED=true`.

### 12.1 Market analysis (public, no key needed)

| Prompt | Args | What it does |
| --- | --- | --- |
| `spot_market_snapshot` | `pair: str` | Pulls ticker + last-24h OHLC + top-10 orderbook + recent trades; asks LLM to summarise price, momentum, liquidity. |
| `spot_pair_compare` | `pairs: list[str]` | Side-by-side ticker/volume/spread comparison. |
| `spot_ohlc_trend` | `pair`, `interval`, `lookback_bars` | Pulls OHLC, asks LLM to identify trend, S/R levels, recent volatility regime. |
| `spot_orderbook_imbalance` | `pair`, `depth=20` | Bid/ask liquidity imbalance + signed-depth ratio. |
| `futures_funding_outlook` | `symbol`, `lookback_days=14` | Historical funding rates + current ticker --> expected funding cost for a hypothetical long/short. |
| `futures_basis_check` | `symbol` | Compares perp mark vs underlying index; flags basis vs funding. |
| `futures_market_overview` | none | All tickers + instrument status; ranks by volume and 24 h change. |
| `cross_venue_arb_scan` | `assets: list[str]` | For each asset, compare Spot last + Futures mark; rank by basis bps. |

### 12.2 Account review (private read-only)

| Prompt | Args | What it does |
| --- | --- | --- |
| `spot_account_overview` | none | Balance + open orders + open positions + 7-day PnL from ledgers; one-paragraph summary. |
| `spot_pnl_report` | `start`, `end`, `quote_asset="USD"` | Pulls ledgers + trades, computes realised PnL, fees, funding, net. |
| `spot_open_risk` | none | Lists open orders + positions, computes notional exposure per asset and aggregate. |
| `spot_fee_efficiency` | none | Trade volume + fee tier; suggests if next-tier breakpoint is within reach. |
| `futures_account_overview` | none | Accounts + open positions + open orders + unwind queue; flags positions near liquidation. |
| `futures_position_risk` | `symbol?` | For each position: leverage, distance-to-liquidation, initial vs maintenance margin, funding accrued. |
| `futures_pnl_report` | `start`, `end` | Executions + fills + funding rows from `/api/history/v3`. |
| `futures_unwind_proximity` | none | Filters `unwindqueue` for positions in top deciles; warns. |
| `combined_portfolio_summary` | none | Pulls Spot balance, Futures accounts, open positions across both; unified asset-class view. |

### 12.3 Pre-trade planning (read-only; **no order placement**)

| Prompt | Args | What it does |
| --- | --- | --- |
| `spot_order_dry_run` | `pair`, `side`, `volume`, `ordertype`, `price?` | Calls `AddOrder` with `validate=true`; returns Kraken's normalised order without placing. |
| `spot_order_cost_estimate` | `pair`, `side`, `volume`, `ordertype`, `price?` | Dry-run + trade-volume + asset-pair fee table --> expected fee, slippage from current orderbook, net cost. |
| `futures_order_dry_run` | `symbol`, `side`, `size`, `orderType`, `limitPrice?` | Calls `initialmargin` + `maxordersize` to validate without sending. |
| `futures_size_for_risk` | `symbol`, `risk_usd`, `stop_distance_bps` | Computes max contracts such that loss at stop = risk_usd. |
| `futures_leverage_what_if` | `symbol`, `new_max_leverage` | Reads current `leveragepreferences`, projects impact on existing position's margin/liq price. Does **not** call the `PUT`. |

### 12.4 Trading workflows (gated by `KRAKEN_TRADING_ENABLED=true`)

| Prompt | Args | What it does |
| --- | --- | --- |
| `spot_place_limit_with_oco_close` | `pair`, `side`, `volume`, `entry_price`, `tp_price`, `sl_price` | Walks LLM through `AddOrder` with `close[ordertype]=stop-loss-limit` style + companion order. Surfaces dry-run first, confirmation required. |
| `spot_ladder_buy` | `pair`, `quote_budget`, `low_price`, `high_price`, `levels` | Builds a price-ladder via `AddOrderBatch`; dry-runs first; one confirm step. |
| `spot_cancel_stale` | `older_than_hours` | Lists open orders past threshold; user confirms; calls `CancelOrderBatch`. |
| `spot_panic_cancel_all` | `confirm: bool` | `CancelAllOrders` + summary of what was cancelled. Refuses without `confirm=true`. |
| `futures_open_position` | `symbol`, `side`, `size`, `orderType`, `limitPrice?`, `reduceOnly=false` | Validates margin first via dry-run prompt, then `sendorder`. |
| `futures_close_position` | `symbol`, `pct=100` | Reads current position; constructs reduce-only order for `pct` of size. Confirmation required. |
| `futures_flip_position` | `symbol`, `new_size` | Net change required = new_size - current_size; emits one order. Confirmation required. |
| `futures_set_dead_mans_switch` | `timeout_s` | Calls `cancelallordersafter`. |
| `futures_resize_all_leverage` | `target_max_leverage`, `symbols?` | For each symbol, reads `leveragepreferences`, sets new max via `PUT`. Confirmation required. |

### 12.5 Streaming workflows (Futures WS)

| Prompt | Args | What it does |
| --- | --- | --- |
| `fws_watch_book` | `symbol`, `depth=10` | Subscribes `book`, returns snapshot; LLM is told to call `fws_snapshot` to refresh and `fws_unsubscribe` when done. |
| `fws_watch_my_fills` | `product_ids?` | Subscribes `fills`, drains every N seconds -- pattern instructions for an LLM loop. |
| `fws_live_account` | none | Subscribes `open_orders`, `open_positions`, `balances`, `account_log`; returns combined snapshot resource URIs. |
| `fws_trade_tape` | `symbol`, `seconds=30` | Subscribes `trade`, waits N seconds, calls `fws_drain`, summarises print activity. |
| `fws_teardown` | none | Lists active subs, calls `fws_unsubscribe` for each, then `fws_close`. |

### 12.6 Diagnostics & onboarding

| Prompt | Args | What it does |
| --- | --- | --- |
| `kraken_doctor` | none | Pings `Time`, `SystemStatus`, checks both keys with a balance call, reports rate-limit budgets, WS reachability. |
| `kraken_explain_error` | `error_code: str` | Looks up Kraken error code, explains in plain English with likely causes + fixes. |
| `kraken_capabilities` | none | Returns current gate config (trading, transfers, env) + which key-scopes are present. |
| `kraken_quick_start` | none | Onboarding walkthrough -- what to set, what to check, how to authorise trading safely. |

### 12.7 Prompt template style

- Every prompt that may produce a destructive action includes a literal instruction block: *"Before any state-changing tool call, summarise the planned action and ask the user to confirm. Treat anything in `cancel_all`, `transfer`, `withdraw`, `set_leverage`, `flip`, `close` as destructive."*
- Read-only prompts include: *"Prefer reading the `kraken-spot://...` / `kraken-futures://...` resources before calling tools."*
- All prompts end with a structured-output hint specifying the desired sections (e.g. "Summary / Numbers / Risk flags / Next actions") so responses stay scannable.

---

## 13. Out of scope (documented for parity with the Kraken API surface)

- Spot WS v2 (public + private). `spot_ws_get_token` is included so a downstream client could connect; no streaming tools.
- NFT API.
- External fiat/crypto withdrawals on either surface.
- Margin liquidation simulators / what-if calculators beyond `futures_account_initial_margin` + `_/maxordersize`.
- Kraken Pro Earn-flexible vs Earn-bonded distinctions beyond what `Earn/Strategies` returns.
