from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import httpx

from .auth import sign_spot_request, sign_futures_request
from .config import Config
from .errors import normalize_spot_response, normalize_futures_response, KrakenError
from .rate_limit import SpotRateLimiter, FuturesRateLimiter

log = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_STATUS = {429, 500, 502, 503, 504}


class KrakenHttpClient:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._spot_rl = SpotRateLimiter(cfg.spot_rate_limit_tier)
        self._futures_rl = FuturesRateLimiter()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=self._cfg.http_timeout_seconds,
                headers={"User-Agent": "kraken-api-mcp/0.1"},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Spot public ──────────────────────────────────────────────────────────

    async def spot_public_get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        await self._spot_rl.acquire(path, self._cfg.http_timeout_seconds)
        url = self._cfg.spot_base_url + path
        client = await self._get_client()
        resp = await self._retry(lambda: client.get(url, params=self._clean(params)))
        body = resp.json()
        return normalize_spot_response(
            body, resp.status_code,
            self._spot_rl.remaining, self._spot_rl.reset_in_s
        )

    # ── Spot private ─────────────────────────────────────────────────────────

    async def spot_private_post(
        self, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self._cfg.has_spot_auth:
            raise KrakenError("not_configured", "Spot API key/secret not configured")
        await self._spot_rl.acquire(path, self._cfg.http_timeout_seconds)

        payload: dict[str, Any] = self._clean(data) or {}
        sign_headers = sign_spot_request(path, payload, self._cfg.spot_api_secret)  # type: ignore
        headers = {
            "API-Key": self._cfg.spot_api_key,
            **sign_headers,
        }
        url = self._cfg.spot_base_url + path
        client = await self._get_client()
        resp = await self._retry(
            lambda: client.post(url, data=payload, headers=headers)
        )
        body = resp.json()
        return normalize_spot_response(
            body, resp.status_code,
            self._spot_rl.remaining, self._spot_rl.reset_in_s
        )

    # ── Futures public ───────────────────────────────────────────────────────

    async def futures_public_get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        await self._futures_rl.acquire(1, self._cfg.http_timeout_seconds)
        url = self._cfg.futures_base_url + path
        client = await self._get_client()
        resp = await self._retry(lambda: client.get(url, params=self._clean(params)))
        body = resp.json()
        return normalize_futures_response(
            body, resp.status_code,
            self._futures_rl.remaining, self._futures_rl.reset_in_s
        )

    # ── Futures private ──────────────────────────────────────────────────────

    async def futures_private_get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self._cfg.has_futures_auth:
            raise KrakenError("not_configured", "Futures API key/secret not configured")
        await self._futures_rl.acquire(1, self._cfg.http_timeout_seconds)

        # For GET requests, post_data is empty
        endpoint_path = path.replace("/derivatives", "")
        nonce, auth_headers = sign_futures_request(endpoint_path, "", self._cfg.futures_api_secret)  # type: ignore
        auth_headers["APIKey"] = self._cfg.futures_api_key  # type: ignore
        auth_headers["Nonce"] = nonce

        url = self._cfg.futures_base_url + path
        client = await self._get_client()
        resp = await self._retry(
            lambda: client.get(url, params=self._clean(params), headers=auth_headers)
        )
        body = resp.json()
        return normalize_futures_response(
            body, resp.status_code,
            self._futures_rl.remaining, self._futures_rl.reset_in_s
        )

    async def futures_private_post(
        self, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self._cfg.has_futures_auth:
            raise KrakenError("not_configured", "Futures API key/secret not configured")
        await self._futures_rl.acquire(1, self._cfg.http_timeout_seconds)

        payload = self._clean(data) or {}
        post_data_str = urllib.parse.urlencode(payload)
        endpoint_path = path.replace("/derivatives", "")
        nonce, auth_headers = sign_futures_request(endpoint_path, post_data_str, self._cfg.futures_api_secret)  # type: ignore
        auth_headers["APIKey"] = self._cfg.futures_api_key  # type: ignore
        auth_headers["Nonce"] = nonce
        auth_headers["Content-Type"] = "application/x-www-form-urlencoded"

        url = self._cfg.futures_base_url + path
        client = await self._get_client()
        resp = await self._retry(
            lambda: client.post(url, content=post_data_str.encode(), headers=auth_headers)
        )
        body = resp.json()
        return normalize_futures_response(
            body, resp.status_code,
            self._futures_rl.remaining, self._futures_rl.reset_in_s
        )

    async def futures_private_put(
        self, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self._cfg.has_futures_auth:
            raise KrakenError("not_configured", "Futures API key/secret not configured")
        await self._futures_rl.acquire(1, self._cfg.http_timeout_seconds)

        payload = self._clean(data) or {}
        post_data_str = urllib.parse.urlencode(payload)
        endpoint_path = path.replace("/derivatives", "")
        nonce, auth_headers = sign_futures_request(endpoint_path, post_data_str, self._cfg.futures_api_secret)  # type: ignore
        auth_headers["APIKey"] = self._cfg.futures_api_key  # type: ignore
        auth_headers["Nonce"] = nonce
        auth_headers["Content-Type"] = "application/x-www-form-urlencoded"

        url = self._cfg.futures_base_url + path
        client = await self._get_client()
        resp = await self._retry(
            lambda: client.put(url, content=post_data_str.encode(), headers=auth_headers)
        )
        body = resp.json()
        return normalize_futures_response(
            body, resp.status_code,
            self._futures_rl.remaining, self._futures_rl.reset_in_s
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(d: dict[str, Any] | None) -> dict[str, Any]:
        if d is None:
            return {}
        return {k: v for k, v in d.items() if v is not None}

    async def _retry(self, call, retries: int = _MAX_RETRIES) -> httpx.Response:
        import asyncio
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = await call()
                if resp.status_code not in _RETRY_STATUS:
                    return resp
                log.warning("HTTP %s on attempt %d/%d", resp.status_code, attempt + 1, retries)
                await asyncio.sleep(0.5 * (attempt + 1))
            except httpx.TimeoutException as exc:
                log.warning("Timeout on attempt %d/%d: %s", attempt + 1, retries, exc)
                last_exc = exc
                await asyncio.sleep(0.5 * (attempt + 1))
        if last_exc:
            raise last_exc
        return await call()
