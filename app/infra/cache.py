import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CACHE_LOOKUPS

logger = get_logger(__name__)

NOT_FOUND = "__NOT_FOUND__"


class UrlCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._settings = get_settings()

    def _key(self, code: str) -> str:
        return f"url:{code}"

    def _lock_key(self, code: str) -> str:
        return f"urllock:{code}"

    async def get(self, code: str) -> dict[str, Any] | None | str:
        try:
            raw = await self._redis.get(self._key(code))
        except Exception:
            logger.warning("cache_get_failed", code=code)
            CACHE_LOOKUPS.labels(result="error").inc()
            return None

        if raw is None:
            CACHE_LOOKUPS.labels(result="miss").inc()
            return None

        if raw == NOT_FOUND:
            CACHE_LOOKUPS.labels(result="negative").inc()
            return NOT_FOUND

        CACHE_LOOKUPS.labels(result="hit").inc()
        return json.loads(raw)

    async def set_found(self, code: str, payload: dict[str, Any]) -> None:
        expires_at = payload.get("expires_at")
        ttl = self._settings.cache_ttl_seconds
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                remaining = (exp - datetime.now(timezone.utc)).total_seconds()
                ttl = max(1, min(ttl, int(remaining)))
            except ValueError:
                pass

        try:
            await self._redis.set(self._key(code), json.dumps(payload), ex=ttl)
        except Exception:
            logger.warning("cache_set_failed", code=code)

    async def set_negative(self, code: str) -> None:
        try:
            await self._redis.set(
                self._key(code), NOT_FOUND, ex=self._settings.negative_cache_ttl_seconds
            )
        except Exception:
            logger.warning("cache_negative_set_failed", code=code)

    async def invalidate(self, code: str) -> None:
        try:
            await self._redis.delete(self._key(code))
        except Exception:
            logger.warning("cache_invalidate_failed", code=code)

    async def acquire_lock(self, code: str) -> bool:
        try:
            return bool(
                await self._redis.set(
                    self._lock_key(code), "1", nx=True, ex=self._settings.cache_lock_seconds
                )
            )
        except Exception:
            return False

    async def release_lock(self, code: str) -> None:
        try:
            await self._redis.delete(self._lock_key(code))
        except Exception:
            pass
