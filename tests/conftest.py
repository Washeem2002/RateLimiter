import os

os.environ.setdefault("IP_HASH_SALT", "test-salt")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/9")
os.environ.setdefault("BASE_URL", "http://testserver")

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routers import health, redirect, urls
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.infra.cache import UrlCache
from app.infra.rate_limiter import RateLimiter
from app.models.models import Base
from app.repositories.click_repo import ClickRepository
from app.repositories.url_repo import UrlRepository
from app.services.id_generator import IdGenerator
from app.services.url_service import UrlService


@pytest.fixture
async def engine() -> AsyncIterator:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session_factory(engine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def fake_redis() -> AsyncIterator:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


def build_app(session_factory, redis) -> FastAPI:
    settings = get_settings()
    cache = UrlCache(redis)
    limiter = RateLimiter(redis)

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    def make_service():
        session = session_factory()
        return UrlService(
            UrlRepository(session),
            ClickRepository(session),
            IdGenerator(redis, UrlRepository(session), settings.id_counter_offset),
            cache,
            redis,
            settings,
        )

    app.dependency_overrides[get_url_service] = make_service
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    app.include_router(urls.router)
    app.include_router(health.router)
    app.include_router(redirect.router)
    return app


@pytest.fixture
async def client(session_factory, fake_redis) -> AsyncIterator:
    app = build_app(session_factory, fake_redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
