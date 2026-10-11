import asyncio
from datetime import date, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import WORKER_BATCH_SIZE, WORKER_LAG
from app.models.models import Base
from app.repositories.click_repo import ClickRepository

configure_logging()
logger = get_logger(__name__)


class ClickConsumer:
    def __init__(self, redis: Redis, session_factory: async_sessionmaker) -> None:
        settings = get_settings()
        self._redis = redis
        self._session_factory = session_factory
        self._stream = settings.click_stream_key
        self._group = settings.click_stream_group
        self._consumer = settings.worker_consumer_name
        self._batch_size = settings.worker_batch_size
        self._poll = settings.worker_poll_interval_seconds
        self._running = True

    async def setup(self) -> None:
        try:
            await self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
            logger.info("consumer_group_created", stream=self._stream, group=self._group)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                logger.warning("consumer_group_create_failed", error=str(exc))

    async def reclaim_pending(self) -> None:
        try:
            entries = await self._redis.xautoclaim(
                self._stream,
                self._group,
                self._consumer,
                min_idle_time=60000,
                start_id="0-0",
                count=self._batch_size,
            )
            messages = entries[1] if len(entries) > 1 else []
            if messages:
                logger.info("reclaimed_pending", count=len(messages))
                await self._process(messages, ack=True)
        except Exception as exc:
            logger.warning("reclaim_failed", error=str(exc))

    async def run(self) -> None:
        await self.setup()
        await self.reclaim_pending()

        while self._running:
            try:
                await self._consume_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("consumer_loop_error", error=str(exc))
                await asyncio.sleep(self._poll)

    async def _consume_once(self) -> None:
        try:
            response = await self._redis.xreadgroup(
                groupname=self._group,
                consumername=self._consumer,
                streams={self._stream: ">"},
                count=self._batch_size,
                block=int(self._poll * 1000),
            )
        except Exception as exc:
            logger.warning("xreadgroup_failed", error=str(exc))
            await asyncio.sleep(self._poll)
            return

        if not response:
            return

        for _stream_name, messages in response:
            if messages:
                await self._process(messages, ack=True)

    async def _process(self, messages: list, ack: bool) -> None:
        rows: list[dict] = []
        rollup: dict[tuple[str, date, str], int] = {}

        for _message_id, data in messages:
            try:
                clicked_at = datetime.fromisoformat(data["clicked_at"])
            except (KeyError, ValueError):
                clicked_at = datetime.now()

            day = clicked_at.date()
            short_code = data.get("short_code", "")
            referrer = data.get("referrer") or "direct"
            ip_hash = data.get("ip_hash") or ""

            rows.append(
                {
                    "short_code": short_code,
                    "clicked_at": clicked_at,
                    "referrer": data.get("referrer"),
                    "user_agent": data.get("user_agent"),
                    "ip_hash": ip_hash,
                }
            )

            key = (short_code, day, referrer)
            rollup[key] = rollup.get(key, 0) + 1

        if rows:
            async with self._session_factory() as session:
                repo = ClickRepository(session)
                await repo.bulk_insert(rows)
                for (short_code, day, referrer), delta in rollup.items():
                    await repo.upsert_daily_rollup(short_code, day, delta)
                    await repo.upsert_referrer_rollup(short_code, day, referrer, delta)
                await repo.commit()

            WORKER_BATCH_SIZE.observe(len(rows))
            logger.info("batch_inserted", count=len(rows))

        if ack:
            for message_id, _ in messages:
                try:
                    await self._redis.xack(self._stream, self._group, message_id)
                except Exception as exc:
                    logger.warning("xack_failed", error=str(exc))

    async def update_lag(self) -> None:
        try:
            info = await self._redis.xinfo_groups(self._stream)
            for group in info:
                if group.get("name") == self._group:
                    lag = group.get("lag", 0) or 0
                    WORKER_LAG.set(lag)
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    consumer = ClickConsumer(redis, session_factory)

    logger.info("worker_starting", consumer=settings.worker_consumer_name)

    try:
        await consumer.run()
    finally:
        await redis.aclose()
        await engine.dispose()
        logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
