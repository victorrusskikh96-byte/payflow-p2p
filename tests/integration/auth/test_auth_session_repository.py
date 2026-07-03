"""Интеграционные тесты SQLAlchemy-репозитория refresh-сессий."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.auth.domain import AuthSession, AuthSessionStatus
from payflow.modules.auth.infrastructure import SQLAlchemyAuthSessionRepository
from payflow.modules.auth.infrastructure.models import AuthSessionModel
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для интеграционного теста.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    users = SQLAlchemyUserRepository(async_session)
    return await users.create(User(email=f"{uuid4()}@example.com"))


async def test_create_auth_session(async_session: AsyncSession) -> None:
    """Проверяет создание refresh-сессии в PostgreSQL.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyAuthSessionRepository(async_session)
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash="refresh-token-hash",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )

    created_session = await repository.create(session)

    stored_session = await async_session.get(AuthSessionModel, created_session.id)
    assert stored_session is not None
    assert stored_session.user_id == user.id
    assert stored_session.refresh_token_hash == "refresh-token-hash"
    assert stored_session.status == AuthSessionStatus.ACTIVE.value


async def test_get_auth_session_by_id(async_session: AsyncSession) -> None:
    """Проверяет поиск refresh-сессии по id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyAuthSessionRepository(async_session)
    created_session = await repository.create(
        AuthSession(
            user_id=user.id,
            refresh_token_hash="refresh-token-hash",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )

    found_session = await repository.get_by_id(created_session.id)

    assert found_session == created_session


async def test_get_active_auth_session_by_refresh_token_hash(
    async_session: AsyncSession,
) -> None:
    """Проверяет поиск активной refresh-сессии по hash refresh token.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyAuthSessionRepository(async_session)
    created_session = await repository.create(
        AuthSession(
            user_id=user.id,
            refresh_token_hash="active-refresh-token-hash",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )

    found_session = await repository.get_active_by_refresh_token_hash(
        "active-refresh-token-hash"
    )

    assert found_session == created_session
    assert await repository.exists_active(created_session.id)


async def test_revoke_auth_session(async_session: AsyncSession) -> None:
    """Проверяет отзыв refresh-сессии.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyAuthSessionRepository(async_session)
    created_session = await repository.create(
        AuthSession(
            user_id=user.id,
            refresh_token_hash="revoked-refresh-token-hash",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )

    revoked_session = await repository.revoke(created_session.id)

    assert revoked_session is not None
    assert revoked_session.status is AuthSessionStatus.REVOKED
    assert revoked_session.revoked_at is not None
    assert not await repository.exists_active(created_session.id)
    assert (
        await repository.get_active_by_refresh_token_hash("revoked-refresh-token-hash")
        is None
    )


async def test_expired_auth_session_is_not_active(
    async_session: AsyncSession,
) -> None:
    """Проверяет, что истекшая refresh-сессия не считается active.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyAuthSessionRepository(async_session)
    expired_session = await repository.create(
        AuthSession(
            user_id=user.id,
            refresh_token_hash="expired-refresh-token-hash",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )

    found_session = await repository.get_active_by_refresh_token_hash(
        "expired-refresh-token-hash"
    )

    assert found_session is None
    assert not await repository.exists_active(expired_session.id)


async def test_auth_session_requires_existing_user(
    async_session: AsyncSession,
) -> None:
    """Проверяет внешний ключ refresh-сессии на users.id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyAuthSessionRepository(async_session)

    with pytest.raises(IntegrityError):
        await repository.create(
            AuthSession(
                user_id=uuid4(),
                refresh_token_hash="orphan-refresh-token-hash",
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        )
