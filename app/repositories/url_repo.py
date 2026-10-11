from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Url, UrlSequence


class UrlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> Url | None:
        stmt = select(Url).where(Url.short_code == code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def get_by_idempotency_key(self, key: str) -> Url | None:
        stmt = select(Url).where(Url.idempotency_key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        short_code: str,
        long_url: str,
        expires_at: datetime | None,
        idempotency_key: str | None,
        row_id: int | None = None,
    ) -> Url:
        url = Url(
            id=row_id,
            short_code=short_code,
            long_url=long_url,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
        )
        self._session.add(url)
        await self._session.commit()
        await self._session.refresh(url)
        return url

    async def soft_delete(self, code: str) -> bool:
        stmt = (
            update(Url)
            .where(Url.short_code == code, Url.is_deleted.is_(False))
            .values(is_deleted=True)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def sequence_next(self, name: str) -> int:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(UrlSequence)
            .values(id=name, value=1)
            .on_conflict_do_update(
                index_elements=[UrlSequence.id],
                set_={"value": UrlSequence.value + 1},
            )
            .returning(UrlSequence.value)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return int(result.scalar_one())
