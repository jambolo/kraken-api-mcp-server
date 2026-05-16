# Security Audit — Kraken API MCP Server

**Date:** 2026-05-16
**Scope:** All code under `kraken_mcp/`, configuration, and deployment surface.
**Threat model:** API-key theft, unauthorized fund movement, accidental exposure via logs/MCP responses, replay attacks, supply-chain risk from MCP host process.

---

## 1. Sensitive Data Inventory

| Asset | Location | Sensitivity | Notes |
| --- | --- | --- | --- |
| `KRAKEN_SPOT_API_SECRET` | env → [config.py:57](kraken_mcp/config.py#L57) | **CRITICAL** | Base64 HMAC key. Possession = full Spot account control. |
| `KRAKEN_FUTURES_API_SECRET` | env → [config.py:59](kraken_mcp/config.py#L59) | **CRITICAL** | Base64 HMAC key. Possession = full Futures control. |
| `KRAKEN_SPOT_API_KEY` | env → [config.py:56](kraken_mcp/config.py#L56) | High | Identifies caller. Useless without secret but exposes account on enumeration. |
| `KRAKEN_FUTURES_API_KEY` | env → [config.py:58](kraken_mcp/config.py#L58) | High | Same as above for Futures. |
| WS signed challenge | [ws/client.py:29](kraken_mcp/ws/client.py#L29) | High | Authorizes private WS feeds for session lifetime. Memory-resident. |
| WS challenge string | [ws/client.py:28](kraken_mcp/ws/client.py#L28) | Medium | Server-issued; harmless alone but part of auth chain. |
| Account data in WS rings | [ws/state.py:7](kraken_mcp/ws/state.py#L7) (`fills`, `account_log`, `deposits_withdrawals`, `notifications_auth`) | Medium | Financial PII; persists until drained or process exits. |
| Spot WS auth token | [spot/exports.py:90](kraken_mcp/spot/exports.py#L90) (`GetWebSocketsToken`) | Medium | Returned to MCP client; 15-min TTL. Token grants WS auth. |
| Deposit addresses | [spot/funding.py:25](kraken_mcp/spot/funding.py#L25) | Medium | Returned to MCP client. Spoofing risk on a compromised display. |

---

## 2. Findings

Severity scale: **CRITICAL** (exploitation = financial loss) / **HIGH** (likely leak vector) / **MEDIUM** (defense-in-depth gap) / **LOW** (informational).

### 2.1 CRITICAL

#### C-1. Trading + transfers gated only by env vars, not per-call auth

[server.py](kraken_mcp/server.py), [spot/trading.py:13-15](kraken_mcp/spot/trading.py#L13-L15), [spot/funding.py:72-73](kraken_mcp/spot/funding.py#L72-L73)

Once `KRAKEN_TRADING_ENABLED=true` is set, **any** caller of the MCP server can invoke `spot_trade_add_order`, `spot_trade_cancel_all_orders` (after `confirm=true`), etc. MCP itself has no per-tool authorization; the MCP host (e.g. Claude Desktop) acts on behalf of whoever drives the conversation. A prompt injection in retrieved web content or a malicious document could trigger arbitrary trades.

**Mitigation owned by user (cannot fix in code):**

- Treat `KRAKEN_TRADING_ENABLED=true` like a loaded gun. Default to `false`. Toggle only when actively trading; restore to `false` immediately after.
- Use a **Kraken API key with restricted permissions** (Kraken supports per-key permission flags: Query Funds, Modify Orders, Withdraw Funds). Disable withdrawals on the key entirely. Limit to specific IP if running on a fixed host.
- Set a **withdrawal allowlist** in your Kraken account settings as a defense layer outside this server's control.

### 2.2 HIGH

#### H-1. `Config` dataclass has no secret-masking `__repr__`

[config.py:8-19](kraken_mcp/config.py#L8-L19)

`@dataclass` auto-generates `__repr__` that prints every field. Any `log.info("cfg=%s", cfg)`, `print(cfg)`, traceback that includes `cfg` in a local frame, or pickling will leak all four secrets in plaintext. No current call site does this, but the foot-gun is loaded.

**Fix (Claude can do):** Override `__repr__` / `__str__` on `Config` to mask secret fields.

#### H-2. `spot/exports.py` bypasses `KrakenHttpClient`

[spot/exports.py:53-75](kraken_mcp/spot/exports.py#L53-L75)

`spot_export_retrieve` constructs its own `httpx.AsyncClient`, signs and sends the request inline. Implications:

- Bypasses rate limiter (`SpotRateLimiter`).
- Bypasses retry policy (`_retry`).
- Bypasses error envelope normalization.
- Different exception surface — any error here may include the request object (with auth headers) in the traceback.
- Returns up to ~50 MB of CSV/TSV (export size unbounded) base64-encoded into a single MCP response. No size cap.

**Fix (Claude can do):** Add a binary-fetch method to `KrakenHttpClient` (e.g. `spot_private_post_raw`) and have `spot_export_retrieve` use it. Add a max-response-size guard.

#### H-3. Nonce uses millisecond resolution; collision under concurrency

[auth.py:11-12](kraken_mcp/auth.py#L11-L12)

```python
def _nonce() -> str:
    return str(int(time.time() * 1000))
```

Two concurrent async calls in the same millisecond produce identical nonces. Kraken requires nonces to be **strictly monotonically increasing per key**; collision/regression returns `EAPI:Invalid nonce` and, worse, can permanently break the key if nonce window drifts. The rate-limiter lock serializes Spot calls per process, but the Futures rate-limiter lock and concurrent Spot+Futures calls do not protect this.

**Fix (Claude can do):** Use microsecond resolution (`int(time.time() * 1_000_000)`) or a monotonically-incrementing counter guarded by a lock. Persist last nonce per key across process restarts is ideal but out of scope.

#### H-4. WS reconnect storm exposure on bad credentials

[ws/client.py:120-133](kraken_mcp/ws/client.py#L120-L133)

`_run_loop` reconnects on **any** exception with exponential back-off, but the back-off resets after a successful connect. If the WS accepts the connection but rejects auth (challenge fails, key revoked), the loop will spin at maximum WS frequency once authentication-related disconnects look like normal disconnects. The current `_handle_message` does not distinguish auth-reject events.

**Fix (Claude can do):** Detect auth-error WS messages in `_handle_message`, mark the client as auth-failed, and stop reconnect attempts that depend on auth.

#### H-5. `.gitignore` excludes `.env` but no commit-hook enforcement

[.gitignore:27-30](.gitignore#L27-L30)

`.gitignore` is correct (`.env`, `.env.*`, `!.env.example`). However, nothing prevents a user from `git add -f .env`, and there is no secret-scanning pre-commit hook.

**Mitigation owned by user:**

- Install `gitleaks` or `trufflehog` as a pre-commit hook.
- Enable GitHub push-protection / secret scanning on the repo (free for public; paid for private).
- Rotate any key that has touched a CI environment, shell history, or screen recording.

### 2.3 MEDIUM

#### M-1. Logging at DEBUG could expose payloads

[http_client.py:191](kraken_mcp/http_client.py#L191), [http_client.py:194](kraken_mcp/http_client.py#L194), [ws/client.py:129](kraken_mcp/ws/client.py#L129), [ws/client.py:152](kraken_mcp/ws/client.py#L152)

Current log statements are safe (status codes, exception class + message, no bodies/headers). But if `KRAKEN_LOG_LEVEL=DEBUG` is set and a future change adds `log.debug("req: %s", request)`, signed headers would be logged. Document that `KRAKEN_LOG_LEVEL=DEBUG` is for development only and may produce sensitive output.

**Fix (Claude can do):** Add a comment to [config.py:65](kraken_mcp/config.py#L65) and the `KRAKEN_LOG_LEVEL` row in [README.md:44](README.md#L44) warning that DEBUG logs may include sensitive data.

#### M-2. WS state is in-process, unbounded by total memory

[ws/state.py](kraken_mcp/ws/state.py)

- Ring buffers cap at 1000 messages **per (feed, product_id)**. A user that subscribes to `trade` for hundreds of symbols accumulates hundreds of thousands of cached messages.
- L2 book dicts have **no eviction**; a long-running session for many symbols grows unbounded.
- All cached account data (fills, ledger, balances) lives in plaintext memory until process exit.

**Fix (Claude can do):** Cap total tracked symbols. Drop oldest book on overflow. Document the in-memory persistence in the README.

#### M-3. No bind-address or transport-level authentication

[server.py:33](kraken_mcp/server.py#L33), [\_\_main\_\_.py](kraken_mcp/__main__.py)

Server uses MCP stdio transport. This is correct for a single-user local MCP host (Claude Desktop launches the process per-user). **Risk emerges only** if the user repurposes this to HTTP/SSE transport — there is no auth layer; anyone reaching the port can call any tool.

**Mitigation owned by user:** Do not expose this server over a network without adding a reverse proxy with auth, mTLS, or wrapping with `mcp-proxy`'s auth modes. The MCP stdio model assumes the local user is the only caller.

#### M-4. Subprocess inherits parent environment

[\_\_main\_\_.py](kraken_mcp/__main__.py)

`os.getenv` in [config.py:46-66](kraken_mcp/config.py#L46-L66) reads from the process environment, which is inherited from the MCP host (Claude Desktop, etc.). On macOS/Linux this is readable by other processes of the same user via `/proc/<pid>/environ`. On Windows, similar exposure exists via debugger APIs.

**Mitigation owned by user:**

- Prefer a credential helper (OS keychain) over env vars for production. (Code change required — see action A-7.)
- On shared workstations, ensure no other user has access. Don't run the MCP host as a service-account that other people can `su` to.

#### M-5. `confirm=True` for cancel-all is the only guard; no rate-limit on confirmations

[spot/trading.py:140-153](kraken_mcp/spot/trading.py#L140-L153)

A prompt-injected agent that drives the MCP tool with `confirm=True` immediately destroys all open orders. The argument is a single boolean; the LLM may auto-pass it if it "looks like" the right call.

**Fix (Claude can do):** Require `confirm` to be a non-trivial string (e.g. account ID or `"CANCEL-ALL-OPEN-ORDERS"`) so the LLM cannot easily emit it from a generic prompt-injection. This raises the bar significantly.

#### M-6. `futures_transfer` accepts `amount: float`

[futures/transfers.py:22](kraken_mcp/futures/transfers.py#L22), [futures/transfers.py:43](kraken_mcp/futures/transfers.py#L43)

Other transfer/order tools use `str` to preserve precision; this one uses `float`. IEEE-754 rounding could move a fractional cent / satoshi. Not a security bug, but it is an integrity bug for funds movement.

**Fix (Claude can do):** Change to `str`, send through unchanged.

### 2.4 LOW / Informational

#### L-1. No secret zeroing in memory

Python strings are immutable; secrets remain in heap until GC'd and possibly in interned-string pool. Mitigating this requires `ctypes` tricks and rarely succeeds against process memory dumps. Accept as residual risk.

#### L-2. HTTP timeout default 30s is shared with rate-limit wait deadline

[rate_limit.py:42](kraken_mcp/rate_limit.py#L42), [http_client.py:46](kraken_mcp/http_client.py#L46)

If rate-limiter acquire waits 25s, the subsequent HTTP request has only 5s budget. Not a security issue but causes confusing TimeoutErrors. Out of scope.

#### L-3. No SSL pinning

`httpx.AsyncClient(http2=True)` uses system CA trust. A user with a malicious root CA installed could be MITM'd. Standard for non-banking software; documenting only.

#### L-4. CI workflow exposure (verify)

[.github/workflows/python-ci.yml](.github/workflows/python-ci.yml) — confirm tests do not require real Kraken credentials. Currently tests use dummy base64 secrets ([tests/test_auth.py](tests/test_auth.py)), so this is OK. Re-verify if secrets are ever added to CI.

**Mitigation owned by user:** If you ever add integration tests that hit real Kraken, use GitHub Actions encrypted secrets and **demo-environment keys only** (`KRAKEN_FUTURES_ENV=demo`).

#### L-5. Returned data includes financial PII

All `data` fields in tool responses (balances, fills, deposits) become part of the MCP transcript that may be logged by the MCP host (Claude Desktop conversation history). Out of scope for this server; document for users.

---

## 3. Action Plan

### 3.1 Actions Claude can perform (code changes)

Numbered in suggested priority order:

- **A-1.** Add masking `__repr__` / `__str__` to `Config`. (H-1, ~5 lines)
- **A-2.** Bump nonce to microsecond resolution and serialize with a lock. (H-3, ~10 lines)
- **A-3.** Refactor `spot_export_retrieve` to use `KrakenHttpClient`; add a binary response method; cap response size. (H-2, ~30 lines)
- **A-4.** Detect auth-failure WS messages and halt reconnect; surface state via `fws_status`. (H-4, ~20 lines)
- **A-5.** Require a non-trivial confirmation string for `spot_trade_cancel_all_orders` and equivalent futures tool. (M-5, ~10 lines)
- **A-6.** Change `futures_transfer` and `futures_transfer_subaccount` amount type from `float` to `str`. (M-6, ~4 lines)
- **A-7.** Add OS-keychain support (`keyring` package) as an optional secret source falling back to env. (M-4, ~40 lines)
- **A-8.** Cap total WS-tracked symbols; evict oldest book on overflow; document memory behavior. (M-2)
- **A-9.** Add a DEBUG-may-leak warning comment to `KRAKEN_LOG_LEVEL` in config and README. (M-1, ~4 lines)

### 3.2 Actions the user must perform

These cannot be fixed in code:

- **U-1.** **Use Kraken API keys with least-privilege permissions.** In Kraken's account settings, create dedicated keys for this MCP server with **withdrawal disabled**, optionally restricted to specific IPs.
- **U-2.** **Configure a Kraken withdrawal allowlist** as defense-in-depth — independent of this server.
- **U-3.** **Keep `KRAKEN_TRADING_ENABLED=false` and `KRAKEN_TRANSFERS_ENABLED=false` by default.** Toggle on only during active use; restore immediately.
- **U-4.** **Test with `KRAKEN_FUTURES_ENV=demo` first** whenever validating new tool flows.
- **U-5.** **Install secret-scanning pre-commit hook** (`gitleaks` or `trufflehog`) before any contributor pushes from a machine that has held real credentials.
- **U-6.** **Enable GitHub push-protection / secret scanning** on the upstream repo.
- **U-7.** **Rotate any key that has been pasted into a chat, exported to a shell, or committed (even briefly)** — assume permanent compromise.
- **U-8.** **Do not expose this MCP server over the network.** It assumes single-local-user stdio. If remote access is needed, wrap with `mcp-proxy` + auth, or run inside a private VPN/SSH tunnel.
- **U-9.** **Review MCP host logs (e.g. Claude Desktop conversation history)** — account data returned by tools is stored there in plaintext. Consider periodic purging.
- **U-10.** **Audit conversations for prompt-injection attempts** before enabling trading. A malicious upstream document, web page, or copied text can attempt to drive tool calls. The cancel-all and transfer tools are highest-value targets.
- **U-11.** **Set Kraken account two-factor authentication** with a hardware token (YubiKey) where supported. Out of band but the most effective single control.
- **U-12.** **Monitor Kraken account activity emails** — Kraken sends transactional alerts; treat unexpected ones as incidents requiring immediate key revocation.

### 3.3 Incident response checklist (for the user)

If a key may be compromised:

1. **Revoke immediately** in Kraken account settings — does not require login from the original IP.
2. **Cancel all open orders** manually via the Kraken web UI (do not rely on this server).
3. **Check recent activity** for unauthorized trades/transfers.
4. **Generate new keys** with least-privilege permissions; update `.env`; restart MCP host.
5. **Rotate any other credential** stored alongside (the same env file, same git history, same machine if compromise was local).

---

## 4. Out of Scope

- Supply-chain compromise of `httpx`, `websockets`, `mcp` libraries — mitigated only by pinning and SBOM tooling.
- Kraken API endpoint security (TLS, server-side auth) — trusted.
- Host OS compromise — if the user's machine is rooted, no application-level mitigation matters.
- LLM-side prompt-injection defenses — the responsibility of the MCP host and the user's prompt hygiene, not this server. Server-side mitigations are defense-in-depth only (see M-5, A-5).

---

## 5. Quick Reference — File:Line Index

| Finding | Primary location |
| --- | --- |
| C-1 | [server.py:33](kraken_mcp/server.py#L33), [spot/trading.py:13](kraken_mcp/spot/trading.py#L13) |
| H-1 | [config.py:8](kraken_mcp/config.py#L8) |
| H-2 | [spot/exports.py:53-75](kraken_mcp/spot/exports.py#L53-L75) |
| H-3 | [auth.py:11](kraken_mcp/auth.py#L11) |
| H-4 | [ws/client.py:120-133](kraken_mcp/ws/client.py#L120-L133) |
| H-5 | [.gitignore:27](.gitignore#L27) |
| M-1 | [http_client.py:191](kraken_mcp/http_client.py#L191), [config.py:65](kraken_mcp/config.py#L65) |
| M-2 | [ws/state.py:7](kraken_mcp/ws/state.py#L7) |
| M-3 | [server.py:33](kraken_mcp/server.py#L33) |
| M-4 | [config.py:46](kraken_mcp/config.py#L46) |
| M-5 | [spot/trading.py:140](kraken_mcp/spot/trading.py#L140) |
| M-6 | [futures/transfers.py:22](kraken_mcp/futures/transfers.py#L22) |
