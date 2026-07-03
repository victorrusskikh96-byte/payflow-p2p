"""SQLAlchemy-репозитории auth-сущностей."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.auth.application.repositories import (
    AuthCredentialsRepository,
    AuthSessionRepository,
)
from payflow.modules.auth.domain import AuthCredentials, AuthSession, AuthSessionStatus
from payflow.modules.auth.infrastructure.mappers import (
    auth_credentials_entity_to_model,
    auth_credentials_model_to_entity,
    auth_session_entity_to_model,
    auth_session_model_to_entity,
)
from payflow.modules.auth.infrastructure.models import (
    AuthCredentialsModel,
    AuthSessionModel,
)


class SQLAlchemyAuthCredentialsRepository(AuthCredentialsRepository):
    """Работает с учетными данными через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий учетных данных.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, credentials: AuthCredentials) -> AuthCredentials:
        """Сохраняет учетные данные пользователя.

        Args:
            credentials: Доменная сущность учетных данных.

        Returns:
            Сохраненные учетные данные.
        """
        credentials_model = auth_credentials_entity_to_model(credentials)
        self._session.add(credentials_model)
        await self._session.flush()
        return auth_credentials_model_to_entity(credentials_model)

    async def get_by_user_id(self, user_id: UUID) -> AuthCredentials | None:
        """Возвращает учетные данные по идентификатору пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Учетные данные или None, если запись не найдена.
        """
        statement = select(AuthCredentialsModel).where(
            AuthCredentialsModel.user_id == user_id
        )
        credentials_model = await self._session.scalar(statement)
        if credentials_model is None:
            return None
        return auth_credentials_model_to_entity(credentials_model)


class SQLAlchemyAuthSessionRepository(AuthSessionRepository):
    """Работает с refresh-сессиями через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий refresh-сессий.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, session: AuthSession) -> AuthSession:
        """Сохраняет refresh-сессию.

        Args:
            session: Доменная сущность refresh-сессии.

        Returns:
            Сохраненная refresh-сессия.
        """
        session_model = auth_session_entity_to_model(session)
        self._session.add(session_model)
        await self._session.flush()
        return auth_session_model_to_entity(session_model)

    async def get_by_id(self, session_id: UUID) -> AuthSession | None:
        """Возвращает refresh-сессию по идентификатору.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            Refresh-сессия или None, если запись не найдена.
        """
        session_model = await self._session.get(AuthSessionModel, session_id)
        if session_model is None:
            return None
        return auth_session_model_to_entity(session_model)

    async def get_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        """Возвращает refresh-сессию по хешу refresh token.

        Args:
            refresh_token_hash: Хеш refresh token.

        Returns:
            Refresh-сессия или None, если запись не найдена.
        """
        statement = select(AuthSessionModel).where(
            AuthSessionModel.refresh_token_hash == refresh_token_hash
        )
        session_model = await self._session.scalar(statement)
        if session_model is None:
            return None
        return auth_session_model_to_entity(session_model)

    async def get_active_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        """Возвращает активную refresh-сессию по хешу refresh token.

        Args:
            refresh_token_hash: Хеш refresh token.

        Returns:
            Активная refresh-сессия или None, если запись не найдена.
        """
        statement = select(AuthSessionModel).where(
            AuthSessionModel.refresh_token_hash == refresh_token_hash,
            AuthSessionModel.status == AuthSessionStatus.ACTIVE.value,
            AuthSessionModel.expires_at > datetime.now(UTC),
        )
        session_model = await self._session.scalar(statement)
        if session_model is None:
            return None
        return auth_session_model_to_entity(session_model)

    async def revoke(self, session_id: UUID) -> AuthSession | None:
        """Отзывает refresh-сессию по идентификатору.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            Отозванная refresh-сессия или None, если запись не найдена.
        """
        session_model = await self._session.get(AuthSessionModel, session_id)
        if session_model is None:
            return None

        session = auth_session_model_to_entity(session_model)
        session.revoke()
        session_model.status = session.status.value
        session_model.revoked_at = session.revoked_at
        session_model.updated_at = session.updated_at
        await self._session.flush()
        return auth_session_model_to_entity(session_model)

    async def exists_active(self, session_id: UUID) -> bool:
        """Проверяет существование активной refresh-сессии.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            True, если активная refresh-сессия существует.
        """
        statement = select(
            exists().where(
                AuthSessionModel.id == session_id,
                AuthSessionModel.status == AuthSessionStatus.ACTIVE.value,
                AuthSessionModel.expires_at > datetime.now(UTC),
            )
        )
        return bool(await self._session.scalar(statement))
