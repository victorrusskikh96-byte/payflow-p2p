"""SQLAlchemy-репозиторий пользователей."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.users.application.repositories import UserRepository
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.mappers import (
    user_entity_to_model,
    user_model_to_entity,
)
from payflow.modules.users.infrastructure.models import UserModel


class SQLAlchemyUserRepository(UserRepository):
    """Работает с пользователями через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий пользователей.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, user: User) -> User:
        """Сохраняет нового пользователя в базе данных.

        Args:
            user: Доменная сущность пользователя.

        Returns:
            Сохраненный пользователь.
        """
        user_model = user_entity_to_model(user)
        self._session.add(user_model)
        await self._session.flush()
        return user_model_to_entity(user_model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Возвращает пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Пользователь или None, если запись не найдена.
        """
        user_model = await self._session.get(UserModel, user_id)
        if user_model is None:
            return None
        return user_model_to_entity(user_model)

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает пользователя по нормализованному email.

        Args:
            email: Email пользователя.

        Returns:
            Пользователь или None, если запись не найдена.
        """
        normalized_email = email.strip().lower()
        statement = select(UserModel).where(UserModel.email == normalized_email)
        user_model = await self._session.scalar(statement)
        if user_model is None:
            return None
        return user_model_to_entity(user_model)

    async def exists_by_email(self, email: str) -> bool:
        """Проверяет наличие пользователя с указанным email.

        Args:
            email: Email пользователя.

        Returns:
            True, если пользователь найден.
        """
        normalized_email = email.strip().lower()
        statement = select(exists().where(UserModel.email == normalized_email))
        return bool(await self._session.scalar(statement))
