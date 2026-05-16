import asyncio
import pytest

from kraken_mcp.rate_limit import SpotRateLimiter, FuturesRateLimiter


@pytest.mark.asyncio
async def test_spot_rate_limiter_acquires():
    rl = SpotRateLimiter("intermediate")
    # Should not raise for normal requests
    await rl.acquire("/0/public/Ticker")
    assert rl.remaining < 20


@pytest.mark.asyncio
async def test_spot_rate_limiter_order_endpoints_free():
    rl = SpotRateLimiter("starter")
    initial = rl.remaining
    await rl.acquire("/0/private/AddOrder")
    assert rl.remaining == initial  # order endpoints don't cost counter


@pytest.mark.asyncio
async def test_futures_rate_limiter_acquires():
    rl = FuturesRateLimiter()
    await rl.acquire(1)
    assert rl.remaining == 499


@pytest.mark.asyncio
async def test_spot_rate_limiter_timeout():
    rl = SpotRateLimiter("starter")
    # Drain the bucket
    rl._counter = 0.0
    with pytest.raises(TimeoutError):
        await rl.acquire("/0/private/Balance", timeout=0.01)
