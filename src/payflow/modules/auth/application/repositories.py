"""Интерфейсы репозиториев для учетных данных аутентификации."""

from typing import Protocol
from uuid import UUID

from payflow.modules.auth.domain import AuthCredentials, AuthSession


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


class AuthSessionRepository(Protocol):
    """Определяет контракт хранилища refresh-сессий."""

    async def create(self, session: AuthSession) -> AuthSession:
        """Сохраняет refresh-сессию.

        Args:
            session: Доменная сущность refresh-сессии.

        Returns:
            Сохраненная refresh-сессия.
        """

    async def get_by_id(self, session_id: UUID) -> AuthSession | None:
        """Возвращает refresh-сессию по идентификатору.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            Refresh-сессия или None, если она не найдена.
        """

    async def get_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        """Возвращает refresh-сессию по хешу refresh token.

        Args:
            refresh_token_hash: Хеш refresh token.

        Returns:
            Refresh-сессия или None, если она не найдена.
        """

    async def get_active_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        """Возвращает активную refresh-сессию по хешу refresh token.

        Args:
            refresh_token_hash: Хеш refresh token.

        Returns:
            Активная refresh-сессия или None, если она не найдена.
        """

    async def revoke(self, session_id: UUID) -> AuthSession | None:
        """Отзывает refresh-сессию по идентификатору.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            Отозванная refresh-сессия или None, если она не найдена.
        """

    async def exists_active(self, session_id: UUID) -> bool:
        """Проверяет существование активной refresh-сессии.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            True, если активная refresh-сессия существует.
        """
