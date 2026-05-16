from __future__ import annotations

import collections
from typing import Any


_RING_FEEDS = {"trade", "fills", "account_log", "deposits_withdrawals", "notifications_auth"}
_RING_SIZE = 1000


class WSState:
    """Thread-safe cache of latest WS messages per (feed, product_id)."""

    def __init__(self) -> None:
        # last-message-wins feeds: key = (feed, product_id or "")
        self._latest: dict[tuple[str, str], Any] = {}
        # ring-buffer feeds: key = (feed, product_id or "")
        self._rings: dict[tuple[str, str], collections.deque[Any]] = {}
        # L2 orderbook: key = symbol, value = {"bids": {price: qty}, "asks": {price: qty}}
        self._books: dict[str, dict[str, dict[str, str]]] = {}
        # active subscriptions: set of (feed, product_id or "")
        self._subscriptions: set[tuple[str, str]] = set()

    # ── Subscription tracking ────────────────────────────────────────────────

    def add_subscription(self, feed: str, product_id: str = "") -> None:
        self._subscriptions.add((feed, product_id))

    def remove_subscription(self, feed: str, product_id: str = "") -> None:
        self._subscriptions.discard((feed, product_id))

    def list_subscriptions(self) -> list[dict[str, Any]]:
        result = []
        for feed, pid in sorted(self._subscriptions):
            key = (feed, pid)
            depth = len(self._rings[key]) if key in self._rings else None
            result.append({"feed": feed, "product_id": pid or None, "queue_depth": depth})
        return result

    # ── Message ingestion ────────────────────────────────────────────────────

    def ingest(self, msg: dict[str, Any]) -> None:
        feed = msg.get("feed", "")
        if not feed or feed in ("info", "challenge", "subscribed", "unsubscribed", "error", "heartbeat"):
            return

        # Normalize product key
        product_id: str = msg.get("product_id", "") or ""

        if feed == "book":
            self._ingest_book(msg, product_id)
            return

        key = (feed, product_id)
        if feed in _RING_FEEDS:
            if key not in self._rings:
                self._rings[key] = collections.deque(maxlen=_RING_SIZE)
            self._rings[key].append(msg)
        else:
            self._latest[key] = msg

    def _ingest_book(self, msg: dict[str, Any], symbol: str) -> None:
        if symbol not in self._books:
            self._books[symbol] = {"bids": {}, "asks": {}}
        book = self._books[symbol]

        # Snapshot
        if msg.get("type") == "snapshot":
            book["bids"] = {str(b[0]): str(b[1]) for b in msg.get("bids", [])}
            book["asks"] = {str(a[0]): str(a[1]) for a in msg.get("asks", [])}
            return

        # Delta
        for bid in msg.get("bids", []):
            price, qty = str(bid[0]), str(bid[1])
            if qty == "0" or float(qty) == 0:
                book["bids"].pop(price, None)
            else:
                book["bids"][price] = qty
        for ask in msg.get("asks", []):
            price, qty = str(ask[0]), str(ask[1])
            if qty == "0" or float(qty) == 0:
                book["asks"].pop(price, None)
            else:
                book["asks"][price] = qty

    # ── Read operations ──────────────────────────────────────────────────────

    def snapshot(self, feed: str, product_id: str = "") -> Any:
        if feed == "book":
            book = self._books.get(product_id)
            if book is None:
                return {"status": "not-subscribed"}
            bids = sorted(book["bids"].items(), key=lambda x: float(x[0]), reverse=True)
            asks = sorted(book["asks"].items(), key=lambda x: float(x[0]))
            return {"feed": "book", "product_id": product_id, "bids": bids, "asks": asks}

        key = (feed, product_id)
        if feed in _RING_FEEDS:
            ring = self._rings.get(key)
            if ring is None:
                return {"status": "not-subscribed"}
            return {"feed": feed, "product_id": product_id or None, "messages": list(ring)}

        val = self._latest.get(key)
        if val is None:
            return {"status": "not-subscribed"}
        return val

    def drain(self, feed: str, product_id: str = "", max_msgs: int = 1000) -> list[Any]:
        """Return up to max_msgs buffered messages and clear the buffer."""
        key = (feed, product_id)
        if feed == "book":
            # Drain is a snapshot for book
            return [self.snapshot(feed, product_id)]

        if feed in _RING_FEEDS:
            ring = self._rings.get(key)
            if not ring:
                return []
            msgs = list(ring)[-max_msgs:]
            ring.clear()
            return msgs

        val = self._latest.pop(key, None)
        return [val] if val else []
