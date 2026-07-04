"""SQLAlchemy-модели таблиц ledger."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from payflow.shared.infrastructure.database import Base


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
