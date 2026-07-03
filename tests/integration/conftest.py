"""Общие фикстуры интеграционных тестов с PostgreSQL."""

from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from payflow.core.config import settings
from payflow.modules.auth.infrastructure.models import (
    AuthCredentialsModel,
    AuthSessionModel,
)
from payflow.modules.users.infrastructure.models import UserModel


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    """Применяет миграции Alembic перед интеграционными тестами.

    Returns:
        Итератор управления жизненным циклом фикстуры.
    """
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    yield


@pytest.fixture(scope="session")
async def integration_engine(
    migrated_database: None,
) -> AsyncIterator[AsyncEngine]:
    """Создает engine для интеграционных тестов.

    Args:
        migrated_database: Фикстура с примененными миграциями.

    Returns:
        Асинхронный итератор с SQLAlchemy engine.
    """
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )

    yield engine

    await engine.dispose()


@pytest.fixture(scope="session")
def async_session_factory(
    integration_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Создает фабрику асинхронных сессий для тестов.

    Args:
        integration_engine: Engine интеграционной базы данных.

    Returns:
        Фабрика асинхронных SQLAlchemy-сессий.
    """
    return async_sessionmaker(integration_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def clean_database(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Очищает таблицы пользователей и auth-данных вокруг каждого теста.

    Args:
        async_session_factory: Фабрика асинхронных сессий.

    Returns:
        Асинхронный итератор управления очисткой базы.
    """
    async with async_session_factory() as session:
        await session.execute(delete(AuthSessionModel))
        await session.execute(delete(AuthCredentialsModel))
        await session.execute(delete(UserModel))
        await session.commit()

    yield

    async with async_session_factory() as session:
        await session.execute(delete(AuthSessionModel))
        await session.execute(delete(AuthCredentialsModel))
        await session.execute(delete(UserModel))
        await session.commit()


@pytest.fixture
async def async_session(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Выдает асинхронную сессию для одного интеграционного теста.

    Args:
        async_session_factory: Фабрика асинхронных сессий.

    Returns:
        Асинхронный итератор с SQLAlchemy-сессией.
    """
    async with async_session_factory() as session:
        yield session
        await session.rollback()
