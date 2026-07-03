"""Интерфейсы репозиториев для работы с пользователями."""

from typing import Protocol
from uuid import UUID

from payflow.modules.users.domain import User


class UserRepository(Protocol):
    """Определяет контракт хранилища пользователей для use cases."""

    async def create(self, user: User) -> User:
        """Сохраняет нового пользователя.

        Args:
            user: Доменная сущность пользователя.

        Returns:
            Сохраненный пользователь.
        """

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Возвращает пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Пользователь или None, если он не найден.
        """

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает пользователя по email.

        Args:
            email: Email пользователя.

        Returns:
            Пользователь или None, если он не найден.
        """

    async def exists_by_email(self, email: str) -> bool:
        """Проверяет существование пользователя с указанным email.

        Args:
            email: Email пользователя.

        Returns:
            True, если пользователь существует.
        """
