"""Миграция создания таблицы учетных данных.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-03 00:00:02.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создает таблицу учетных данных пользователей.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.create_table(
        "auth_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_credentials_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_auth_credentials_user_id"),
    )


def downgrade() -> None:
    """Удаляет таблицу учетных данных пользователей.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Если база данных отклоняет DDL-операцию.
    """
    op.drop_table("auth_credentials")
