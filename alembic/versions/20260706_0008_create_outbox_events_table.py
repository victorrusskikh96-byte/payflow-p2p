"""Миграция создания таблицы outbox events.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создает таблицу outbox events.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'FAILED')",
            name="ck_outbox_events_status_allowed",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_outbox_events_attempts_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index(
        "ix_outbox_events_aggregate_type_aggregate_id",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )
    op.create_index(
        "ix_outbox_events_occurred_at",
        "outbox_events",
        ["occurred_at"],
    )
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"])


def downgrade() -> None:
    """Удаляет таблицу outbox events.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.drop_index("ix_outbox_events_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_occurred_at", table_name="outbox_events")
    op.drop_index(
        "ix_outbox_events_aggregate_type_aggregate_id",
        table_name="outbox_events",
    )
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_table("outbox_events")
