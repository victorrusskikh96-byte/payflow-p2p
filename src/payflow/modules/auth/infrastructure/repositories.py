"""SQLAlchemy-репозиторий учетных данных аутентификации."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.auth.application.repositories import AuthCredentialsRepository
from payflow.modules.auth.domain import AuthCredentials
from payflow.modules.auth.infrastructure.mappers import (
    auth_credentials_entity_to_model,
    auth_credentials_model_to_entity,
)
from payflow.modules.auth.infrastructure.models import AuthCredentialsModel


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
