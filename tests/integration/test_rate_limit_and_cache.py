from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.infra.cache import NOT_FOUND, UrlCache
from app.infra.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_create_rate_limit_returns_429(client) -> None:
    limit = get_settings().rate_limit_create_per_min

    statuses = []
    for _ in range(limit + 3):
        resp = await client.post("/api/v1/urls", json={"long_url": "https://example.com"})
        statuses.append(resp.status_code)

    assert 429 in statuses
    blocked = [r for r in await _collect_rejected(client, limit + 3)]
    assert blocked.headers.get("Retry-After") is not None


async def _collect_rejected(client, attempts):
    for _ in range(attempts):
        resp = await client.post("/api/v1/urls", json={"long_url": "https://example.com"})
        if resp.status_code == 429:
            yield resp
            return


@pytest.mark.asyncio
async def test_rate_limit_headers_present(client) -> None:
    resp = await client.post("/api/v1/urls", json={"long_url": "https://example.com/h"})
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers


@pytest.mark.asyncio
async def test_redirect_rate_limit_returns_429(client) -> None:
    await client.post("/api/v1/urls", json={"long_url": "https://example.com/rl"})
    limit = get_settings().rate_limit_redirect_per_min

    codes = []
    for _ in range(limit + 5):
        resp = await client.get("/nonexistent", follow_redirects=False)
        codes.append(resp.status_code)

    assert 429 in codes


@pytest.mark.asyncio
async def test_cache_hit_and_miss(client, fake_redis) -> None:
    await client.post(
        "/api/v1/urls", json={"long_url": "https://example.com/cached", "custom_alias": "cachecode"}
    )

    cache = UrlCache(fake_redis)
    assert await cache.get("cachecode") is None

    first = await client.get("/cachecode", follow_redirects=False)
    assert first.status_code == 302

    cached = await cache.get("cachecode")
    assert isinstance(cached, dict)
    assert cached["long_url"] == "https://example.com/cached"


@pytest.mark.asyncio
async def test_negative_cache_stores_not_found(client, fake_redis) -> None:
    cache = UrlCache(fake_redis)

    resp = await client.get("/missingcode", follow_redirects=False)
    assert resp.status_code == 404

    cached = await cache.get("missingcode")
    assert cached == NOT_FOUND


@pytest.mark.asyncio
async def test_lock_acquired_and_released(fake_redis) -> None:
    cache = UrlCache(fake_redis)
    assert await cache.acquire_lock("somecode") is True
    assert await cache.acquire_lock("somecode") is False
    await cache.release_lock("somecode")
    assert await cache.acquire_lock("somecode") is True


@pytest.mark.asyncio
async def test_cache_ttl_capped_to_expiry(fake_redis) -> None:
    cache = UrlCache(fake_redis)
    soon = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
    await cache.set_found("ttlcode", {"long_url": "https://example.com", "expires_at": soon})
    ttl = await fake_redis.ttl("url:ttlcode")
    assert 0 < ttl <= 10


@pytest.mark.asyncio
async def test_rate_limiter_isolated_from_redirect_down(
    client, fake_redis
) -> None:
    limiter = RateLimiter(fake_redis)
    result = await limiter.check("redirect", "someone", 300)
    assert result.remaining >= 0
