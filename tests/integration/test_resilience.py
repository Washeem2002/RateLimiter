import pytest


@pytest.mark.asyncio
async def test_redirect_survives_stream_failure(client, fake_redis) -> None:
    created = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/resilient", "custom_alias": "resilient"},
    )
    assert created.status_code == 201

    async def broken_xadd(*args, **kwargs):
        raise ConnectionError("stream down")

    original = fake_redis.xadd
    fake_redis.xadd = broken_xadd

    try:
        resp = await client.get("/resilient", follow_redirects=False)
    finally:
        fake_redis.xadd = original

    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/resilient"


@pytest.mark.asyncio
async def test_redirect_works_when_cache_set_fails(client, fake_redis) -> None:
    await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/nocache", "custom_alias": "nocache"},
    )

    async def broken_set(*args, **kwargs):
        raise ConnectionError("cache down")

    original = fake_redis.set
    fake_redis.set = broken_set
    try:
        resp = await client.get("/nocache", follow_redirects=False)
    finally:
        fake_redis.set = original

    assert resp.status_code == 302
