"""Фикстуры E2E API-тестов с тестовой PostgreSQL-базой."""

from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from payflow.core.config import settings
from payflow.core.database import get_async_session
from payflow.main import create_app
from payflow.modules.auth.infrastructure.models import (
    AuthCredentialsModel,
    AuthSessionModel,
)
from payflow.modules.users.infrastructure.models import UserModel


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[None]:
    """Применяет миграции Alembic перед E2E API-тестами.

    Returns:
        Итератор управления жизненным циклом фикстуры.
    """
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    yield


@pytest.fixture(scope="session")
async def e2e_async_session_factory(
    migrated_database: None,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Создает фабрику асинхронных сессий для E2E API-тестов.

    Args:
        migrated_database: Фикстура с примененными миграциями.

    Returns:
        Асинхронный итератор с фабрикой SQLAlchemy-сессий.
    """
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()


@pytest.fixture
async def clean_auth_database(
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Очищает таблицы пользователей и auth-данных вокруг API-теста.

    Args:
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.

    Returns:
        Асинхронный итератор управления очисткой базы.
    """
    async with e2e_async_session_factory() as session:
        await session.execute(delete(AuthSessionModel))
        await session.execute(delete(AuthCredentialsModel))
        await session.execute(delete(UserModel))
        await session.commit()

    yield

    async with e2e_async_session_factory() as session:
        await session.execute(delete(AuthSessionModel))
        await session.execute(delete(AuthCredentialsModel))
        await session.execute(delete(UserModel))
        await session.commit()


@pytest.fixture
async def api_client(
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
    clean_auth_database: None,
) -> AsyncIterator[AsyncClient]:
    """Создает HTTP-клиент FastAPI с тестовой сессией базы данных.

    Args:
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
        clean_auth_database: Фикстура очистки auth-таблиц.

    Returns:
        Асинхронный итератор с HTTP-клиентом.
    """

    async def override_get_async_session() -> AsyncIterator[AsyncSession]:
        """Выдает SQLAlchemy-сессию из тестовой фабрики.

        Returns:
            Асинхронный итератор с SQLAlchemy-сессией.
        """
        async with e2e_async_session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_async_session] = override_get_async_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
