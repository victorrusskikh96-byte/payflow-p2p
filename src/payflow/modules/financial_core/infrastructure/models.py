"""SQLAlchemy-модели финансового ядра."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from payflow.shared.infrastructure.database import Base


class WalletModel(Base):
    """Описывает ORM-представление пользовательского кошелька."""

    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_wallets_user_id_currency"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(length=16), nullable=False)
    status: Mapped[str] = mapped_column(String(length=32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WalletBalanceModel(Base):
    """Описывает ORM-представление проекции баланса кошелька."""

    __tablename__ = "wallet_balances"
    __table_args__ = (
        CheckConstraint(
            "available_amount_minor >= 0",
            name="ck_wallet_balances_available_amount_minor_non_negative",
        ),
        CheckConstraint(
            "locked_amount_minor >= 0",
            name="ck_wallet_balances_locked_amount_minor_non_negative",
        ),
    )

    wallet_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    available_amount_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    locked_amount_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    currency: Mapped[str] = mapped_column(String(length=16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class LedgerTransactionModel(Base):
    """Описывает ORM-представление ledger transaction."""

    __tablename__ = "ledger_transactions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'COMMITTED', 'FAILED')",
            name="ck_ledger_transactions_status_allowed",
        ),
        UniqueConstraint(
            "operation_id",
            name="uq_ledger_transactions_operation_id",
        ),
        Index("ix_ledger_transactions_operation_id", "operation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    operation_type: Mapped[str] = mapped_column(String(length=32), nullable=False)
    status: Mapped[str] = mapped_column(String(length=32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class LedgerEntryModel(Base):
    """Описывает ORM-представление immutable ledger entry."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="ck_ledger_entries_amount_minor_positive",
        ),
        CheckConstraint(
            "direction IN ('DEBIT', 'CREDIT')",
            name="ck_ledger_entries_direction_allowed",
        ),
        Index("ix_ledger_entries_wallet_id", "wallet_id"),
        Index("ix_ledger_entries_transaction_id", "transaction_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    transaction_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("ledger_transactions.id"),
        nullable=False,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wallets.id"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(length=16), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(length=16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TransferModel(Base):
    """Описывает ORM-представление пользовательского P2P-перевода."""

    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="ck_transfers_amount_minor_positive",
        ),
        CheckConstraint(
            "sender_wallet_id != recipient_wallet_id",
            name="ck_transfers_sender_recipient_wallets_differ",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name="ck_transfers_status_allowed",
        ),
        UniqueConstraint("operation_id", name="uq_transfers_operation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
    )
    sender_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    sender_wallet_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wallets.id"),
        nullable=False,
    )
    recipient_wallet_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wallets.id"),
        nullable=False,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(length=16), nullable=False)
    status: Mapped[str] = mapped_column(String(length=32), nullable=False)
    ledger_transaction_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("ledger_transactions.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


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
