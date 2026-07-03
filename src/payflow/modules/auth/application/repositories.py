"""Интерфейсы репозиториев для учетных данных аутентификации."""

from typing import Protocol
from uuid import UUID

from payflow.modules.auth.domain import AuthCredentials


class AuthCredentialsRepository(Protocol):
    """Определяет контракт хранилища учетных данных пользователей."""

    async def create(self, credentials: AuthCredentials) -> AuthCredentials:
        """Сохраняет учетные данные пользователя.

        Args:
            credentials: Доменная сущность учетных данных.

        Returns:
            Сохраненные учетные данные.
        """

    async def get_by_user_id(self, user_id: UUID) -> AuthCredentials | None:
        """Возвращает учетные данные по идентификатору пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Учетные данные или None, если они не найдены.
        """
