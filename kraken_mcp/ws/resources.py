from __future__ import annotations

import json
from typing import Any

from ..config import Config
from .state import WSState


def register(mcp: Any, cfg: Config, state: WSState) -> None:

    @mcp.resource("kraken-futures-ws://book/{symbol}")
    async def ws_book(symbol: str) -> str:
        """Cached Kraken Futures WebSocket order book snapshot for a symbol.

        Returns the current L2 order book maintained from WebSocket book feed deltas.
        Format: {feed, product_id, bids: [[price, qty], ...], asks: [[price, qty], ...]}
        with bids sorted best (highest) first and asks sorted best (lowest) first.

        Returns {status: 'not-subscribed'} until fws_subscribe_book is called for this symbol.
        For live streaming data call fws_snapshot after subscribing.
        """
        return json.dumps(state.snapshot("book", symbol))

    @mcp.resource("kraken-futures-ws://ticker/{symbol}")
    async def ws_ticker(symbol: str) -> str:
        """Latest Kraken Futures WebSocket ticker message for a symbol (last-message-wins cache).

        Contains mark price, best bid/ask with sizes, last trade price,
        24-hour volume, open interest, and funding rate for perpetuals.

        Returns {status: 'not-subscribed'} until fws_subscribe_ticker or
        fws_subscribe_ticker_lite is called for this symbol.
        """
        return json.dumps(state.snapshot("ticker", symbol))

    @mcp.resource("kraken-futures-ws://open-orders")
    async def ws_open_orders() -> str:
        """Latest Kraken Futures WebSocket open orders snapshot (last-message-wins cache).

        Reflects the most recent open_orders feed message which contains the
        full set of open orders at that moment. Each order includes symbol, side,
        type, size, filled size, limit/stop price, and status.

        Returns {status: 'not-subscribed'} until fws_subscribe_open_orders is called.
        Requires Futures API credentials.
        """
        return json.dumps(state.snapshot("open_orders"))

    @mcp.resource("kraken-futures-ws://open-positions")
    async def ws_open_positions() -> str:
        """Latest Kraken Futures WebSocket open positions snapshot (last-message-wins cache).

        Reflects the most recent open_positions feed message: symbol, side, size,
        average entry price, mark price, unrealised PnL, and liquidation price.

        Returns {status: 'not-subscribed'} until fws_subscribe_open_positions is called.
        Requires Futures API credentials.
        """
        return json.dumps(state.snapshot("open_positions"))

    @mcp.resource("kraken-futures-ws://balances")
    async def ws_balances() -> str:
        """Latest Kraken Futures WebSocket account balances snapshot (last-message-wins cache).

        Reflects the most recent balances feed message: cash balance, margin balance,
        available funds, initial margin, and maintenance margin per collateral currency.

        Returns {status: 'not-subscribed'} until fws_subscribe_balances is called.
        Requires Futures API credentials.
        """
        return json.dumps(state.snapshot("balances"))

    @mcp.resource("kraken-futures-ws://fills")
    async def ws_fills() -> str:
        """Ring buffer of the last 1000 Kraken Futures WebSocket fill messages.

        Each fill includes symbol, side, price, quantity, fee, fill type
        (maker/taker), and timestamp. The buffer is not cleared by reading this resource;
        use fws_drain to retrieve and clear fills since the last check.

        Returns {status: 'not-subscribed'} until fws_subscribe_fills is called.
        Requires Futures API credentials.
        """
        return json.dumps(state.snapshot("fills"))
