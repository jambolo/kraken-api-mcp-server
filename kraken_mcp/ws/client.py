from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from ..auth import sign_futures_ws_challenge
from ..config import Config
from .state import WSState

log = logging.getLogger(__name__)

_RECONNECT_DELAY_S = 2.0
_MAX_RECONNECT_DELAY_S = 60.0


class FuturesWSClient:
    def __init__(self, cfg: Config, state: WSState) -> None:
        self._cfg = cfg
        self._state = state
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._challenge: str | None = None
        self._signed_challenge: str | None = None
        self._reconnect_count = 0
        self._last_heartbeat: float = 0.0
        # Pending subscriptions to replay after reconnect
        self._pending_subs: list[dict[str, Any]] = []

    # ── Public API ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="futures-ws")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
        self._ready.clear()

    async def wait_ready(self, timeout: float = 10.0) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    async def subscribe(
        self,
        feed: str,
        product_ids: list[str] | None = None,
        private: bool = False,
    ) -> None:
        msg: dict[str, Any] = {"event": "subscribe", "feed": feed}
        if product_ids:
            msg["product_ids"] = product_ids

        if private:
            await self._ensure_challenge()
            if self._challenge and self._signed_challenge:
                msg["api_key"] = self._cfg.futures_api_key
                msg["original_challenge"] = self._challenge
                msg["signed_challenge"] = self._signed_challenge

        self._pending_subs.append(msg)

        # Track in state
        if product_ids:
            for pid in product_ids:
                self._state.add_subscription(feed, pid)
        else:
            self._state.add_subscription(feed)

        if self._ws:
            await self._send(msg)

    async def unsubscribe(self, feed: str, product_ids: list[str] | None = None) -> None:
        msg: dict[str, Any] = {"event": "unsubscribe", "feed": feed}
        if product_ids:
            msg["product_ids"] = product_ids

        if product_ids:
            for pid in product_ids:
                self._state.remove_subscription(feed, pid)
                self._pending_subs = [
                    s for s in self._pending_subs
                    if not (s.get("feed") == feed and pid in (s.get("product_ids") or []))
                ]
        else:
            self._state.remove_subscription(feed)
            self._pending_subs = [s for s in self._pending_subs if s.get("feed") != feed]

        if self._ws:
            await self._send(msg)

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    @property
    def last_heartbeat(self) -> float:
        return self._last_heartbeat

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        delay = _RECONNECT_DELAY_S
        while self._running:
            try:
                await self._connect_and_run()
                delay = _RECONNECT_DELAY_S
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("WS disconnected: %s — reconnecting in %.1fs", exc, delay)
                self._ready.clear()
                self._reconnect_count += 1
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY_S)

    async def _connect_and_run(self) -> None:
        async with websockets.connect(self._cfg.futures_ws_url) as ws:
            self._ws = ws
            log.info("WS connected to %s", self._cfg.futures_ws_url)
            self._ready.set()

            # Replay pending subscriptions
            for sub in list(self._pending_subs):
                await self._send(sub)

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                    await self._handle_message(msg)
                except Exception as exc:
                    log.debug("WS message error: %s", exc)

        self._ws = None

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        event = msg.get("event", "")

        if event == "challenge":
            self._challenge = msg.get("message", "")
            if self._cfg.has_futures_auth and self._challenge:
                self._signed_challenge = sign_futures_ws_challenge(
                    self._challenge, self._cfg.futures_api_secret  # type: ignore
                )
            return

        if msg.get("feed") == "heartbeat":
            import time
            self._last_heartbeat = time.monotonic()

        self._state.ingest(msg)

    async def _ensure_challenge(self) -> None:
        if not self._cfg.has_futures_auth:
            return
        if self._signed_challenge:
            return

        await self.wait_ready(timeout=10.0)
        # Request challenge
        await self._send({"event": "challenge", "api_key": self._cfg.futures_api_key})
        # Wait for it to be processed (max 5s)
        for _ in range(50):
            if self._signed_challenge:
                return
            await asyncio.sleep(0.1)
        log.warning("WS challenge not received in time")

    async def _send(self, msg: dict[str, Any]) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.send(json.dumps(msg))
        else:
            log.debug("WS send skipped — not connected")
