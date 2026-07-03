"""Начальная ревизия базы данных.

Revision ID: 0001
Revises:
Create Date: 2026-07-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет начальную пустую ревизию."""
    pass


def downgrade() -> None:
    """Откатывает начальную пустую ревизию."""
    pass
