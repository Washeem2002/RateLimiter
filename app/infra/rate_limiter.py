import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from redis.asyncio import Redis

from app.core.errors import RateLimitError
from app.core.logging import get_logger
from app.core.metrics import RATE_LIMITED

logger = get_logger(__name__)

_LUA_PATH = Path(__file__).parent / "lua" / "token_bucket.lua"
_LUA_SCRIPT = _LUA_PATH.read_text()

Endpoint = Literal["create", "redirect"]


@dataclass(frozen=True)
class RateLimitResult:
    limit: int
    remaining: int
    retry_after: int | None = None

    @property
    def headers(self) -> dict[str, str]:
        h = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
        }
        if self.retry_after is not None:
            h["Retry-After"] = str(self.retry_after)
        return h


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check(self, endpoint: Endpoint, identity: str, limit_per_min: int) -> RateLimitResult:
        key = f"rl:{endpoint}:{identity}"
        capacity = float(limit_per_min)
        refill_rate = limit_per_min / 60.0
        now = time.time()

        try:
            raw = await self._redis.eval(
                _LUA_SCRIPT, 1, key, capacity, refill_rate, now, 1
            )
        except Exception:
            logger.warning("rate_limiter_unavailable_failing_open", endpoint=endpoint)
            return RateLimitResult(limit=limit_per_min, remaining=limit_per_min)

        allowed = int(raw[0])
        remaining = int(float(raw[1]))
        retry_after = int(raw[2])

        if not allowed:
            RATE_LIMITED.labels(endpoint=endpoint).inc()
            raise RateLimitError(retry_after=max(retry_after, 1))

        return RateLimitResult(limit=limit_per_min, remaining=remaining)
