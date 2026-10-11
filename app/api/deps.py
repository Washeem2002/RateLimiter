from collections.abc import AsyncIterator

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infra.cache import UrlCache
from app.infra.db import get_session
from app.infra.rate_limiter import RateLimiter
from app.infra.redis import get_redis
from app.repositories.click_repo import ClickRepository
from app.repositories.url_repo import UrlRepository
from app.services.analytics_service import hash_ip
from app.services.id_generator import IdGenerator
from app.services.url_service import UrlService


async def get_db_session(session: AsyncSession = Depends(get_session)) -> AsyncIterator[AsyncSession]:
    yield session


def get_settings_dep() -> Settings:
    return get_settings()


def get_url_repo(session: AsyncSession = Depends(get_db_session)) -> UrlRepository:
    return UrlRepository(session)


def get_click_repo(session: AsyncSession = Depends(get_db_session)) -> ClickRepository:
    return ClickRepository(session)


def get_cache(redis: Redis = Depends(get_redis)) -> UrlCache:
    return UrlCache(redis)


def get_rate_limiter(redis: Redis = Depends(get_redis)) -> RateLimiter:
    return RateLimiter(redis)


def get_id_generator(
    url_repo: UrlRepository = Depends(get_url_repo),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> IdGenerator:
    return IdGenerator(redis, url_repo, settings.id_counter_offset)


def get_url_service(
    url_repo: UrlRepository = Depends(get_url_repo),
    click_repo: ClickRepository = Depends(get_click_repo),
    id_gen: IdGenerator = Depends(get_id_generator),
    cache: UrlCache = Depends(get_cache),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> UrlService:
    return UrlService(url_repo, click_repo, id_gen, cache, redis, settings)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"


def hash_client_ip(request: Request) -> str:
    return hash_ip(get_client_ip(request))
