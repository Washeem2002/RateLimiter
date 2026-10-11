from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.errors import ConflictError, GoneError, NotFoundError
from app.core.logging import get_logger
from app.core.metrics import URLS_CREATED
from app.infra.cache import NOT_FOUND, UrlCache
from app.models.models import Url
from app.repositories.click_repo import ClickRepository
from app.repositories.url_repo import UrlRepository
from app.schemas.schemas import (
    DailyClicks,
    TopReferrer,
    UrlCreateRequest,
    UrlMetadataResponse,
    UrlResponse,
    UrlStatsResponse,
)
from app.services.id_generator import IdGenerator
from app.services.url_validator import validate_alias, validate_and_normalize_url

logger = get_logger(__name__)


def _is_expired(url: Url) -> bool:
    if url.expires_at is None:
        return False
    exp = url.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= datetime.now(timezone.utc)


def _to_response(url: Url, base_url: str) -> UrlResponse:
    return UrlResponse(
        short_code=url.short_code,
        short_url=f"{base_url.rstrip('/')}/{url.short_code}",
        long_url=url.long_url,
        created_at=url.created_at,
        expires_at=url.expires_at,
    )


class UrlService:
    def __init__(
        self,
        repo: UrlRepository,
        click_repo: ClickRepository,
        id_gen: IdGenerator,
        cache: UrlCache,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._click_repo = click_repo
        self._id_gen = id_gen
        self._cache = cache
        self._redis = redis
        self._settings = settings

    async def create_url(
        self, payload: UrlCreateRequest, idempotency_key: str | None
    ) -> UrlResponse:
        if idempotency_key:
            existing = await self._repo.get_by_idempotency_key(idempotency_key)
            if existing:
                return _to_response(existing, self._settings.base_url)

        long_url = validate_and_normalize_url(
            payload.long_url, self._settings.base_url
        )

        alias = None
        if payload.custom_alias:
            alias = validate_alias(payload.custom_alias)

        if alias:
            existing_code = await self._repo.get_by_code(alias)
            if existing_code and not existing_code.is_deleted:
                raise ConflictError("custom alias is already in use")
            code = alias
            row_id = None
        else:
            code, row_id = await self._id_gen.next_code()

        try:
            url = await self._repo.create(
                short_code=code,
                long_url=long_url,
                expires_at=payload.expires_at,
                idempotency_key=idempotency_key,
                row_id=row_id,
            )
        except IntegrityError:
            await self._repo.rollback()
            raise ConflictError("could not create url due to a conflict") from None

        URLS_CREATED.inc()

        response = _to_response(url, self._settings.base_url)
        await self._cache.set_found(
            code,
            {
                "long_url": url.long_url,
                "expires_at": url.expires_at.isoformat() if url.expires_at else None,
                "is_deleted": url.is_deleted,
            },
        )
        return response

    async def resolve(self, code: str) -> str:
        cached = await self._cache.get(code)

        if cached == NOT_FOUND:
            raise NotFoundError("short url not found")

        if isinstance(cached, dict):
            if cached.get("is_deleted"):
                raise NotFoundError("short url not found")
            exp = cached.get("expires_at")
            if exp:
                exp_dt = datetime.fromisoformat(exp)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt <= datetime.now(timezone.utc):
                    raise GoneError("short url has expired")
            return cached["long_url"]

        url = await self._repo.get_by_code(code)

        if url is None:
            await self._cache.set_negative(code)
            raise NotFoundError("short url not found")

        if url.is_deleted:
            await self._cache.set_negative(code)
            raise NotFoundError("short url not found")

        if _is_expired(url):
            raise GoneError("short url has expired")

        payload = {
            "long_url": url.long_url,
            "expires_at": url.expires_at.isoformat() if url.expires_at else None,
            "is_deleted": url.is_deleted,
        }
        await self._cache.set_found(code, payload)

        return url.long_url

    async def record_click(self, code: str, meta: dict) -> None:
        event = {
            "short_code": code,
            "clicked_at": datetime.now(timezone.utc).isoformat(),
            "referrer": meta.get("referrer") or "",
            "user_agent": meta.get("user_agent") or "",
            "ip_hash": meta.get("ip_hash") or "",
        }
        try:
            await self._redis.xadd(self._settings.click_stream_key, event)
        except Exception:
            logger.warning("click_stream_publish_failed", code=code)

    async def get_metadata(self, code: str) -> UrlMetadataResponse:
        url = await self._repo.get_by_code(code)
        if url is None or url.is_deleted:
            raise NotFoundError("short url not found")

        return UrlMetadataResponse(
            short_code=url.short_code,
            long_url=url.long_url,
            created_at=url.created_at,
            expires_at=url.expires_at,
            is_deleted=url.is_deleted,
        )

    async def delete_url(self, code: str) -> None:
        url = await self._repo.get_by_code(code)
        if url is None or url.is_deleted:
            raise NotFoundError("short url not found")

        await self._repo.soft_delete(code)
        await self._cache.invalidate(code)

    async def get_stats(self, code: str) -> UrlStatsResponse:
        url = await self._repo.get_by_code(code)
        if url is None or url.is_deleted:
            raise NotFoundError("short url not found")

        total = await self._click_repo.total_clicks(code)
        per_day = await self._click_repo.clicks_per_day(code, days=7)
        referrers = await self._click_repo.top_referrers(code, limit=5)

        return UrlStatsResponse(
            short_code=code,
            total_clicks=total,
            clicks_last_7_days=[
                DailyClicks(day=d.isoformat(), count=c) for d, c in per_day
            ],
            top_referrers=[TopReferrer(referrer=r, count=c) for r, c in referrers],
        )
