"""SQLAlchemy-модель таблицы outbox events."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from payflow.shared.infrastructure.database import Base


class OutboxEventModel(Base):
    """Описывает ORM-представление outbox event."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'FAILED')",
            name="ck_outbox_events_status_allowed",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_outbox_events_attempts_non_negative",
        ),
        Index("ix_outbox_events_status", "status"),
        Index("ix_outbox_events_event_type", "event_type"),
        Index(
            "ix_outbox_events_aggregate_type_aggregate_id",
            "aggregate_type",
            "aggregate_id",
        ),
        Index("ix_outbox_events_occurred_at", "occurred_at"),
        Index("ix_outbox_events_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(length=128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(length=128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(length=128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(length=32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
