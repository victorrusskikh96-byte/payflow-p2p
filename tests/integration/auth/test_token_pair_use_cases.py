"""Интеграционные тесты use cases token pair с PostgreSQL."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.auth.application import (
    IssueTokenPairUseCase,
    RefreshTokenPairUseCase,
    RevokeRefreshSessionUseCase,
)
from payflow.modules.auth.domain import AuthSessionStatus, InvalidRefreshTokenError
from payflow.modules.auth.infrastructure import (
    JWTAccessTokenService,
    SecureRefreshTokenService,
    SQLAlchemyAuthSessionRepository,
    SQLAlchemyTransactionManager,
)
from payflow.modules.auth.infrastructure.models import AuthSessionModel
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


def build_access_token_service() -> JWTAccessTokenService:
    """Создает JWT-сервис для интеграционных тестов.

    Returns:
        Настроенный JWT-сервис access tokens.
    """
    return JWTAccessTokenService(
        secret_key="integration-test-secret-key-with-32-bytes",
        algorithm="HS256",
        access_token_ttl=timedelta(minutes=15),
    )


def build_issue_use_case(async_session: AsyncSession) -> IssueTokenPairUseCase:
    """Собирает use case выдачи token pair на SQLAlchemy.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case выдачи token pair.
    """
    return IssueTokenPairUseCase(
        access_tokens=build_access_token_service(),
        refresh_tokens=SecureRefreshTokenService(),
        sessions=SQLAlchemyAuthSessionRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
        refresh_token_ttl=timedelta(days=30),
    )


def build_refresh_use_case(async_session: AsyncSession) -> RefreshTokenPairUseCase:
    """Собирает use case обновления token pair на SQLAlchemy.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case обновления token pair.
    """
    return RefreshTokenPairUseCase(
        access_tokens=build_access_token_service(),
        refresh_tokens=SecureRefreshTokenService(),
        sessions=SQLAlchemyAuthSessionRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
        refresh_token_ttl=timedelta(days=30),
    )


async def create_committed_user(async_session: AsyncSession) -> User:
    """Создает пользователя и фиксирует транзакцию.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    user = await SQLAlchemyUserRepository(async_session).create(
        User(email=f"{uuid4()}@example.com")
    )
    await async_session.commit()
    return user


async def test_issue_token_pair_creates_auth_session(
    async_session: AsyncSession,
) -> None:
    """Проверяет создание auth session при выдаче token pair.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_committed_user(async_session)
    use_case = build_issue_use_case(async_session)

    token_pair = await use_case.execute(user_id=user.id)

    statement = select(AuthSessionModel).where(AuthSessionModel.user_id == user.id)
    stored_session = await async_session.scalar(statement)

    assert stored_session is not None
    assert stored_session.refresh_token_hash != token_pair.refresh_token
    assert stored_session.status == AuthSessionStatus.ACTIVE.value


async def test_refresh_token_pair_creates_new_session_and_revokes_old(
    async_session: AsyncSession,
) -> None:
    """Проверяет rotation refresh token в PostgreSQL.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_committed_user(async_session)
    issue_use_case = build_issue_use_case(async_session)
    old_pair = await issue_use_case.execute(user_id=user.id)
    refresh_tokens = SecureRefreshTokenService()
    old_refresh_hash = refresh_tokens.hash_refresh_token(old_pair.refresh_token)
    refresh_use_case = build_refresh_use_case(async_session)

    new_pair = await refresh_use_case.execute(refresh_token=old_pair.refresh_token)

    old_session = await async_session.scalar(
        select(AuthSessionModel).where(
            AuthSessionModel.refresh_token_hash == old_refresh_hash
        )
    )
    new_session = await async_session.scalar(
        select(AuthSessionModel).where(
            AuthSessionModel.refresh_token_hash
            == refresh_tokens.hash_refresh_token(new_pair.refresh_token)
        )
    )

    assert old_session is not None
    assert new_session is not None
    assert old_session.status == AuthSessionStatus.REVOKED.value
    assert new_session.status == AuthSessionStatus.ACTIVE.value
    assert new_session.id != old_session.id


async def test_revoked_session_cannot_be_used_again(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ при использовании отозванной refresh-сессии.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_committed_user(async_session)
    token_pair = await build_issue_use_case(async_session).execute(user_id=user.id)
    revoke_use_case = RevokeRefreshSessionUseCase(
        refresh_tokens=SecureRefreshTokenService(),
        sessions=SQLAlchemyAuthSessionRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )
    await revoke_use_case.execute(refresh_token=token_pair.refresh_token)
    refresh_use_case = build_refresh_use_case(async_session)

    with pytest.raises(InvalidRefreshTokenError):
        await refresh_use_case.execute(refresh_token=token_pair.refresh_token)
