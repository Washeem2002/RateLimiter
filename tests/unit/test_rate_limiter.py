import pytest
import fakeredis.aioredis

from app.core.errors import RateLimitError
from app.infra.rate_limiter import RateLimiter


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest.mark.asyncio
async def test_allows_requests_within_limit(redis) -> None:
    limiter = RateLimiter(redis)
    for _ in range(10):
        result = await limiter.check("create", "1.2.3.4", 10)
    assert result.limit == 10
    assert result.remaining >= 0


@pytest.mark.asyncio
async def test_blocks_request_over_limit(redis) -> None:
    limiter = RateLimiter(redis)
    for _ in range(10):
        await limiter.check("create", "5.6.7.8", 10)

    with pytest.raises(RateLimitError) as exc:
        await limiter.check("create", "5.6.7.8", 10)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


@pytest.mark.asyncio
async def test_buckets_are_isolated_per_identity(redis) -> None:
    limiter = RateLimiter(redis)
    for _ in range(10):
        await limiter.check("create", "a", 10)

    with pytest.raises(RateLimitError):
        await limiter.check("create", "a", 10)

    result = await limiter.check("create", "b", 10)
    assert result.remaining >= 0


@pytest.mark.asyncio
async def test_headers_shape(redis) -> None:
    limiter = RateLimiter(redis)
    result = await limiter.check("redirect", "9.9.9.9", 300)
    headers = result.headers
    assert headers["X-RateLimit-Limit"] == "300"
    assert "X-RateLimit-Remaining" in headers


@pytest.mark.asyncio
async def test_fails_open_when_redis_down() -> None:
    class BrokenRedis:
        async def eval(self, *args, **kwargs):
            raise ConnectionError("down")

    limiter = RateLimiter(BrokenRedis())
    result = await limiter.check("create", "1.1.1.1", 10)
    assert result.remaining == 10
