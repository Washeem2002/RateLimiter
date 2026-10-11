import pytest


@pytest.mark.asyncio
async def test_create_redirect_stats_flow(client) -> None:
    create = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/some/long/path", "custom_alias": "flowtest"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["short_code"] == "flowtest"
    assert body["short_url"].endswith("/flowtest")
    assert body["long_url"] == "https://example.com/some/long/path"

    redirect = await client.get("/flowtest", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com/some/long/path"

    meta = await client.get("/api/v1/urls/flowtest")
    assert meta.status_code == 200
    assert meta.json()["short_code"] == "flowtest"

    stats = await client.get("/api/v1/urls/flowtest/stats")
    assert stats.status_code == 200
    assert "total_clicks" in stats.json()


@pytest.mark.asyncio
async def test_create_generates_code_without_alias(client) -> None:
    resp = await client.post("/api/v1/urls", json={"long_url": "https://example.com"})
    assert resp.status_code == 201
    code = resp.json()["short_code"]
    assert len(code) >= 6

    redirect = await client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 302


@pytest.mark.asyncio
async def test_custom_alias_conflict(client) -> None:
    first = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/a", "custom_alias": "taken"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/b", "custom_alias": "taken"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_redirect_not_found(client) -> None:
    resp = await client.get("/doesnotexist", follow_redirects=False)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_expired_returns_410(client) -> None:
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    created = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/expired", "expires_at": past},
    )
    assert created.status_code == 201
    code = created.json()["short_code"]

    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "gone"


@pytest.mark.asyncio
async def test_soft_delete_invalidates_cache(client) -> None:
    created = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/del", "custom_alias": "delcode"},
    )
    assert created.status_code == 201

    first = await client.get("/delcode", follow_redirects=False)
    assert first.status_code == 302

    deleted = await client.delete("/api/v1/urls/delcode")
    assert deleted.status_code == 204

    after = await client.get("/delcode", follow_redirects=False)
    assert after.status_code == 404


@pytest.mark.asyncio
async def test_idempotency_key_returns_same_result(client) -> None:
    headers = {"Idempotency-Key": "abc-123"}
    payload = {"long_url": "https://example.com/idem"}

    first = await client.post("/api/v1/urls", json=payload, headers=headers)
    second = await client.post("/api/v1/urls", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["short_code"] == second.json()["short_code"]


@pytest.mark.asyncio
async def test_idempotency_does_not_leak_across_keys(client) -> None:
    payload = {"long_url": "https://example.com/other"}
    first = await client.post(
        "/api/v1/urls", json=payload, headers={"Idempotency-Key": "key-one"}
    )
    second = await client.post(
        "/api/v1/urls", json=payload, headers={"Idempotency-Key": "key-two"}
    )
    assert first.json()["short_code"] != second.json()["short_code"]


@pytest.mark.asyncio
async def test_invalid_alias_rejected(client) -> None:
    resp = await client.post(
        "/api/v1/urls",
        json={"long_url": "https://example.com/x", "custom_alias": "ab"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_and_ready(client) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = await client.get("/ready")
    assert ready.status_code in (200, 503)
