"""Интеграционные тесты auth use cases с PostgreSQL."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.auth.application import (
    AuthenticateUserUseCase,
    RegisterUserUseCase,
)
from payflow.modules.auth.domain import (
    AuthCredentials,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from payflow.modules.auth.infrastructure import (
    Argon2PasswordHasher,
    SQLAlchemyAuthCredentialsRepository,
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.domain import User, UserStatus
from payflow.modules.users.infrastructure.models import UserModel
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


def build_register_use_case(async_session: AsyncSession) -> RegisterUserUseCase:
    """Собирает use case регистрации на SQLAlchemy-реализациях.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case регистрации пользователя.
    """
    return RegisterUserUseCase(
        users=SQLAlchemyUserRepository(async_session),
        credentials=SQLAlchemyAuthCredentialsRepository(async_session),
        password_hasher=Argon2PasswordHasher(),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


def build_authenticate_use_case(async_session: AsyncSession) -> AuthenticateUserUseCase:
    """Собирает use case аутентификации на SQLAlchemy-реализациях.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case аутентификации пользователя.
    """
    return AuthenticateUserUseCase(
        users=SQLAlchemyUserRepository(async_session),
        credentials=SQLAlchemyAuthCredentialsRepository(async_session),
        password_hasher=Argon2PasswordHasher(),
    )


async def test_register_creates_user_and_auth_credentials(
    async_session: AsyncSession,
) -> None:
    """Проверяет сохранение пользователя и учетных данных при регистрации.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    password = "valid-password"
    use_case = build_register_use_case(async_session)

    user = await use_case.execute(email="User@Example.com", password=password)

    stored_user = await async_session.get(UserModel, user.id)

    assert stored_user is not None
    assert stored_user.email == "user@example.com"
    assert not hasattr(stored_user, "password_hash")

    credentials_repository = SQLAlchemyAuthCredentialsRepository(async_session)
    credentials = await credentials_repository.get_by_user_id(user.id)

    assert credentials is not None
    assert credentials.password_hash != password
    assert Argon2PasswordHasher().verify_password(password, credentials.password_hash)


async def test_repeated_registration_with_same_email_is_forbidden(
    async_session: AsyncSession,
) -> None:
    """Проверяет запрет повторной регистрации одного email.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    use_case = build_register_use_case(async_session)
    await use_case.execute(email="user@example.com", password="valid-password")

    with pytest.raises(EmailAlreadyRegisteredError):
        await use_case.execute(email="USER@example.com", password="valid-password")


async def test_authenticate_succeeds_with_correct_password(
    async_session: AsyncSession,
) -> None:
    """Проверяет успешную аутентификацию с корректным паролем.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    register_use_case = build_register_use_case(async_session)
    user = await register_use_case.execute(
        email="user@example.com",
        password="valid-password",
    )
    authenticate_use_case = build_authenticate_use_case(async_session)

    authenticated_user = await authenticate_use_case.execute(
        email="USER@example.com",
        password="valid-password",
    )

    assert authenticated_user == user


async def test_authenticate_rejects_wrong_password(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ аутентификации при неверном пароле.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    register_use_case = build_register_use_case(async_session)
    await register_use_case.execute(
        email="user@example.com",
        password="valid-password",
    )
    authenticate_use_case = build_authenticate_use_case(async_session)

    with pytest.raises(InvalidCredentialsError):
        await authenticate_use_case.execute(
            email="user@example.com",
            password="wrong-password",
        )


async def test_authenticate_rejects_blocked_user(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ аутентификации заблокированного пользователя.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    users = SQLAlchemyUserRepository(async_session)
    credentials = SQLAlchemyAuthCredentialsRepository(async_session)
    password_hasher = Argon2PasswordHasher()
    user = await users.create(
        User(email="blocked@example.com", status=UserStatus.BLOCKED)
    )
    await credentials.create(
        AuthCredentials(
            user_id=user.id,
            password_hash=password_hasher.hash_password("valid-password"),
        )
    )
    await async_session.commit()
    authenticate_use_case = build_authenticate_use_case(async_session)

    with pytest.raises(InvalidCredentialsError):
        await authenticate_use_case.execute(
            email="blocked@example.com",
            password="valid-password",
        )
