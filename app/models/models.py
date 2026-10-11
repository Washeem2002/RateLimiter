from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class Url(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    long_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )


class ClickEvent(Base):
    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ClickDaily(Base):
    __tablename__ = "click_daily"
    __table_args__ = (UniqueConstraint("short_code", "day", name="uq_click_daily_code_day"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ClickReferrerDaily(Base):
    __tablename__ = "click_referrer_daily"
    __table_args__ = (
        UniqueConstraint("short_code", "day", "referrer", name="uq_click_referrer_daily_key"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    referrer: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UrlSequence(Base):
    __tablename__ = "url_sequences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
