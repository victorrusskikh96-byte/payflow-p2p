"""Миграция создания таблицы P2P-переводов.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создает таблицу P2P-переводов.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.create_table(
        "transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "ledger_transaction_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "amount_minor > 0",
            name="ck_transfers_amount_minor_positive",
        ),
        sa.CheckConstraint(
            "sender_wallet_id != recipient_wallet_id",
            name="ck_transfers_sender_recipient_wallets_differ",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name="ck_transfers_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_transaction_id"],
            ["ledger_transactions.id"],
            name="fk_transfers_ledger_transaction_id_ledger_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_wallet_id"],
            ["wallets.id"],
            name="fk_transfers_recipient_wallet_id_wallets",
        ),
        sa.ForeignKeyConstraint(
            ["sender_user_id"],
            ["users.id"],
            name="fk_transfers_sender_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["sender_wallet_id"],
            ["wallets.id"],
            name="fk_transfers_sender_wallet_id_wallets",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", name="uq_transfers_operation_id"),
    )


def downgrade() -> None:
    """Удаляет таблицу P2P-переводов.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.drop_table("transfers")
