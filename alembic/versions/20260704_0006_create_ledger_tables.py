"""Миграция создания таблиц ledger.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создает таблицы ledger transactions и ledger entries.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.create_table(
        "ledger_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMMITTED', 'FAILED')",
            name="ck_ledger_transactions_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operation_id",
            name="uq_ledger_transactions_operation_id",
        ),
    )
    op.create_index(
        "ix_ledger_transactions_operation_id",
        "ledger_transactions",
        ["operation_id"],
        unique=False,
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "amount_minor > 0",
            name="ck_ledger_entries_amount_minor_positive",
        ),
        sa.CheckConstraint(
            "direction IN ('DEBIT', 'CREDIT')",
            name="ck_ledger_entries_direction_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["ledger_transactions.id"],
            name="fk_ledger_entries_transaction_id_ledger_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name="fk_ledger_entries_wallet_id_wallets",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ledger_entries_transaction_id",
        "ledger_entries",
        ["transaction_id"],
        unique=False,
    )
    op.create_index(
        "ix_ledger_entries_wallet_id",
        "ledger_entries",
        ["wallet_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет таблицы ledger в порядке зависимостей.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.drop_index("ix_ledger_entries_wallet_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_transaction_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index(
        "ix_ledger_transactions_operation_id",
        table_name="ledger_transactions",
    )
    op.drop_table("ledger_transactions")
