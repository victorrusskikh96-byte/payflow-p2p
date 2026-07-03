"""Миграция создания таблиц кошельков и балансов.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-03 00:00:04.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создает таблицы кошельков и проекций балансов.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_wallets_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "currency", name="uq_wallets_user_id_currency"),
    )
    op.create_table(
        "wallet_balances",
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "available_amount_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "locked_amount_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "available_amount_minor >= 0",
            name="ck_wallet_balances_available_amount_minor_non_negative",
        ),
        sa.CheckConstraint(
            "locked_amount_minor >= 0",
            name="ck_wallet_balances_locked_amount_minor_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name="fk_wallet_balances_wallet_id_wallets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wallet_id"),
    )


def downgrade() -> None:
    """Удаляет таблицы проекций балансов и кошельков.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.drop_table("wallet_balances")
    op.drop_table("wallets")
