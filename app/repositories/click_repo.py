from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ClickDaily, ClickEvent, ClickReferrerDaily


class ClickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(self, events: list[dict]) -> None:
        if not events:
            return
        stmt = pg_insert(ClickEvent).values(events)
        await self._session.execute(stmt)
        await self._session.commit()

    async def upsert_daily_rollup(self, short_code: str, day: date, delta: int) -> None:
        stmt = (
            pg_insert(ClickDaily)
            .values(short_code=short_code, day=day, count=delta)
            .on_conflict_do_update(
                index_elements=[ClickDaily.short_code, ClickDaily.day],
                set_={"count": ClickDaily.count + delta},
            )
        )
        await self._session.execute(stmt)

    async def upsert_referrer_rollup(
        self, short_code: str, day: date, referrer: str, delta: int
    ) -> None:
        stmt = (
            pg_insert(ClickReferrerDaily)
            .values(short_code=short_code, day=day, referrer=referrer, count=delta)
            .on_conflict_do_update(
                index_elements=[
                    ClickReferrerDaily.short_code,
                    ClickReferrerDaily.day,
                    ClickReferrerDaily.referrer,
                ],
                set_={"count": ClickReferrerDaily.count + delta},
            )
        )
        await self._session.execute(stmt)

    async def commit(self) -> None:
        await self._session.commit()

    async def total_clicks(self, short_code: str) -> int:
        stmt = select(func.coalesce(func.sum(ClickDaily.count), 0)).where(
            ClickDaily.short_code == short_code
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def clicks_per_day(self, short_code: str, days: int = 7) -> list[tuple[date, int]]:
        since = date.today() - timedelta(days=days - 1)
        stmt = (
            select(ClickDaily.day, ClickDaily.count)
            .where(ClickDaily.short_code == short_code, ClickDaily.day >= since)
            .order_by(ClickDaily.day)
        )
        result = await self._session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def top_referrers(self, short_code: str, limit: int = 5) -> list[tuple[str, int]]:
        stmt = (
            select(ClickReferrerDaily.referrer, func.sum(ClickReferrerDaily.count).label("total"))
            .where(ClickReferrerDaily.short_code == short_code)
            .group_by(ClickReferrerDaily.referrer)
            .order_by(func.sum(ClickReferrerDaily.count).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]
