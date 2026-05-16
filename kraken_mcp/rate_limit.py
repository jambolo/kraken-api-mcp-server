from __future__ import annotations

import asyncio
import time
from typing import Literal


# Spot rate limit tiers: (max_counter, decay_per_second)
_SPOT_TIERS: dict[str, tuple[int, float]] = {
    "starter": (15, 0.33),
    "intermediate": (20, 0.5),
    "pro": (20, 1.0),
}

# Per-endpoint costs for Spot private endpoints (defaults to 1)
_SPOT_COSTS: dict[str, int] = {
    "/0/private/Ledgers": 2,
    "/0/private/TradesHistory": 2,
    "/0/private/AddOrder": 0,       # order endpoints exempt from counter
    "/0/private/CancelOrder": 0,
    "/0/private/CancelAllOrders": 0,
    "/0/private/CancelOrderBatch": 0,
    "/0/private/AddOrderBatch": 0,
    "/0/private/EditOrder": 0,
    "/0/private/AmendOrder": 0,
}


class SpotRateLimiter:
    def __init__(self, tier: Literal["starter", "intermediate", "pro"] = "intermediate"):
        self._max, self._decay = _SPOT_TIERS[tier]
        self._counter: float = self._max
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._counter = min(self._max, self._counter + elapsed * self._decay)
        self._last_refill = now

    async def acquire(self, path: str, timeout: float = 30.0) -> None:
        cost = _SPOT_COSTS.get(path, 1)
        if cost == 0:
            return  # order endpoints not counter-gated

        deadline = time.monotonic() + timeout
        async with self._lock:
            while True:
                self._refill()
                if self._counter >= cost:
                    self._counter -= cost
                    return
                wait = (cost - self._counter) / self._decay
                if time.monotonic() + wait > deadline:
                    raise TimeoutError(f"Rate limit wait {wait:.1f}s exceeds timeout")
                await asyncio.sleep(min(wait, 0.5))

    @property
    def remaining(self) -> int:
        self._refill()
        return int(self._counter)

    @property
    def reset_in_s(self) -> float:
        self._refill()
        needed = self._max - self._counter
        return needed / self._decay if needed > 0 else 0.0


class FuturesRateLimiter:
    """500-unit budget per 10-second rolling window."""

    BUDGET = 500
    WINDOW = 10.0

    def __init__(self) -> None:
        self._tokens: float = self.BUDGET
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        rate = self.BUDGET / self.WINDOW
        self._tokens = min(self.BUDGET, self._tokens + elapsed * rate)
        self._last_refill = now

    async def acquire(self, cost: int = 1, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= cost:
                    self._tokens -= cost
                    return
                rate = self.BUDGET / self.WINDOW
                wait = (cost - self._tokens) / rate
                if time.monotonic() + wait > deadline:
                    raise TimeoutError(f"Rate limit wait {wait:.1f}s exceeds timeout")
                await asyncio.sleep(min(wait, 0.5))

    @property
    def remaining(self) -> int:
        self._refill()
        return int(self._tokens)

    @property
    def reset_in_s(self) -> float:
        self._refill()
        needed = self.BUDGET - self._tokens
        rate = self.BUDGET / self.WINDOW
        return needed / rate if needed > 0 else 0.0
