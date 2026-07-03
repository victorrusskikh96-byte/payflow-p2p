"""Базовый класс декларативных SQLAlchemy-моделей."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Служит общей базой для всех декларативных SQLAlchemy-моделей."""


__all__ = ("Base",)
