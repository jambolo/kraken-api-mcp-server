# kraken-api-mcp

MCP server for the Kraken exchange — Spot REST, Futures REST, and Futures WebSocket via the [Model Context Protocol](https://modelcontextprotocol.io/).

## Features

- **Spot REST** — market data, trading, account/ledger, funding (deposit + internal transfers), earn/staking, subaccounts, data exports
- **Futures REST** — market data, charts, trading, account, preferences, assignment, history v3
- **Futures WebSocket** — subscribe/snapshot/drain pattern with a server-side cache (L2 book, tickers, orders, positions, fills)
- **MCP resources** — assets, pairs, instruments, system status exposed as stable URIs so the LLM can read them without a tool call
- **Safety gates** — trading and transfers are disabled by default; cancel-all requires an explicit `confirm=true` argument
- **No external withdrawals** — intentionally omitted from all surfaces

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/yourusername/kraken-api-mcp.git
cd kraken-api-mcp
uv sync --extra dev
```

## Configuration

Copy `.env.example` to `.env` and fill in your keys. All settings are environment variables — no config file.

| Variable | Default | Description |
| --- | --- | --- |
| `KRAKEN_SPOT_API_KEY` | — | Spot REST private auth. Omit for public-only mode. |
| `KRAKEN_SPOT_API_SECRET` | — | Base64 Spot secret. Required with key. |
| `KRAKEN_FUTURES_API_KEY` | — | Futures REST + WS auth. |
| `KRAKEN_FUTURES_API_SECRET` | — | Base64 Futures secret. Required with key. |
| `KRAKEN_FUTURES_ENV` | `live` | `live` or `demo` (uses `demo-futures.kraken.com`). |
| `KRAKEN_TRADING_ENABLED` | `false` | Set `true` to enable order placement/edit/cancel, earn allocate/deallocate, leverage/PnL prefs. |
| `KRAKEN_TRANSFERS_ENABLED` | `false` | Set `true` to enable internal wallet transfers and subaccount transfers. |
| `KRAKEN_SPOT_RATE_LIMIT_TIER` | `intermediate` | `starter`, `intermediate`, or `pro`. |
| `KRAKEN_HTTP_TIMEOUT_SECONDS` | `30` | HTTP request timeout. |
| `KRAKEN_LOG_LEVEL` | `INFO` | `INFO` or `DEBUG`. |

## Usage

### stdio transport (MCP host)

```bash
uv run python -m kraken_mcp
```

Configure your MCP host (e.g. Claude Desktop) to launch this command with the required env vars.

### Claude Desktop example

```json
{
  "mcpServers": {
    "kraken": {
      "command": "uv",
      "args": ["run", "python", "-m", "kraken_mcp"],
      "env": {
        "KRAKEN_SPOT_API_KEY": "your-key",
        "KRAKEN_SPOT_API_SECRET": "your-secret",
        "KRAKEN_TRADING_ENABLED": "false"
      }
    }
  }
}
```

## Safety model

| Tool class | Gate |
| --- | --- |
| Public market data | None |
| Private read (balances, orders, history) | API keys |
| Order place / edit / cancel | `KRAKEN_TRADING_ENABLED=true` |
| Cancel **all** orders | `KRAKEN_TRADING_ENABLED=true` + `confirm=true` argument |
| Internal transfers | `KRAKEN_TRANSFERS_ENABLED=true` |
| External withdrawals | **Not implemented** |

The `kraken-safety://config` resource lists which gates are currently open.

## Development

```bash
# Run tests
uv run pytest tests/

# Single test
uv run pytest tests/test_auth.py::test_spot_sign_produces_api_sign_header

# Fail-fast, quiet
uv run pytest tests/ -x -q
```

## Architecture

```text
server.py → spot/{public,trading,account,funding,earn,subaccounts,exports,resources}.py
          → futures/{public,trading,account,prefs,assignment,transfers,subaccounts,history,resources}.py
          → ws/{tools,resources}.py
```

Every tool returns a uniform envelope:

```json
{"ok": true, "data": {}, "errors": [], "raw_status": 200, "rate_limit": {}}
```

See [MCP-Design.md](MCP-Design.md) for full design documentation.

## License

MIT — see [LICENSE](LICENSE).
