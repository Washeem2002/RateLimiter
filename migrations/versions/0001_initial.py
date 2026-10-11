"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("short_code", sa.String(length=20), nullable=False),
        sa.Column("long_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_urls_short_code", "urls", ["short_code"], unique=True)
    op.create_index("ix_urls_idempotency_key", "urls", ["idempotency_key"], unique=True)

    op.create_table(
        "click_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("short_code", sa.String(length=20), nullable=False),
        sa.Column(
            "clicked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_click_events_short_code", "click_events", ["short_code"])
    op.create_index("ix_click_events_clicked_at", "click_events", ["clicked_at"])

    op.create_table(
        "click_daily",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("short_code", sa.String(length=20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("short_code", "day", name="uq_click_daily_code_day"),
    )
    op.create_index("ix_click_daily_short_code", "click_daily", ["short_code"])

    op.create_table(
        "click_referrer_daily",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("short_code", sa.String(length=20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("referrer", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "short_code", "day", "referrer", name="uq_click_referrer_daily_key"
        ),
    )
    op.create_index("ix_click_referrer_daily_short_code", "click_referrer_daily", ["short_code"])

    op.create_table(
        "url_sequences",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("value", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_table("url_sequences")
    op.drop_index("ix_click_referrer_daily_short_code", table_name="click_referrer_daily")
    op.drop_table("click_referrer_daily")
    op.drop_index("ix_click_daily_short_code", table_name="click_daily")
    op.drop_table("click_daily")
    op.drop_index("ix_click_events_clicked_at", table_name="click_events")
    op.drop_index("ix_click_events_short_code", table_name="click_events")
    op.drop_table("click_events")
    op.drop_index("ix_urls_idempotency_key", table_name="urls")
    op.drop_index("ix_urls_short_code", table_name="urls")
    op.drop_table("urls")
