"""SQLAlchemy-модель таблицы P2P-переводов."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from payflow.shared.infrastructure.database import Base


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
