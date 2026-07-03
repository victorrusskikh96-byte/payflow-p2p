"""SQLAlchemy-модели таблиц кошельков и проекций балансов."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
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
