"""Dependency wiring для HTTP API модуля аутентификации."""

from datetime import timedelta
from typing import Annotated, NoReturn

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.core.config import settings
from payflow.core.database import get_async_session
from payflow.modules.auth.application.access_tokens import AccessTokenService
from payflow.modules.auth.application.password_hasher import PasswordHasher
from payflow.modules.auth.application.refresh_tokens import RefreshTokenService
from payflow.modules.auth.application.repositories import (
    AuthCredentialsRepository,
    AuthSessionRepository,
)
from payflow.modules.auth.application.transactions import TransactionManager
from payflow.modules.auth.application.use_cases import (
    AuthenticateUserUseCase,
    GetCurrentUserUseCase,
    IssueTokenPairUseCase,
    RefreshTokenPairUseCase,
    RegisterUserUseCase,
    RevokeRefreshSessionUseCase,
)
from payflow.modules.auth.domain import (
    CurrentUserBlockedError,
    CurrentUserNotFoundError,
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
    UnsupportedTokenTypeError,
)
from payflow.modules.auth.infrastructure.access_tokens import JWTAccessTokenService
from payflow.modules.auth.infrastructure.password_hasher import Argon2PasswordHasher
from payflow.modules.auth.infrastructure.refresh_tokens import SecureRefreshTokenService
from payflow.modules.auth.infrastructure.repositories import (
    SQLAlchemyAuthCredentialsRepository,
    SQLAlchemyAuthSessionRepository,
)
from payflow.modules.auth.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.application.repositories import UserRepository
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserRepository:
    """Создает репозиторий пользователей для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий пользователей.
    """
    return SQLAlchemyUserRepository(session)


def get_auth_credentials_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AuthCredentialsRepository:
    """Создает репозиторий учетных данных для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий учетных данных аутентификации.
    """
    return SQLAlchemyAuthCredentialsRepository(session)


def get_auth_session_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AuthSessionRepository:
    """Создает репозиторий refresh-сессий для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий refresh-сессий.
    """
    return SQLAlchemyAuthSessionRepository(session)


def get_password_hasher() -> PasswordHasher:
    """Создает сервис хеширования паролей.

    Returns:
        Argon2-сервис хеширования паролей.
    """
    return Argon2PasswordHasher()


def get_access_token_service() -> AccessTokenService:
    """Создает сервис выпуска и проверки JWT access tokens.

    Returns:
        JWT-сервис access tokens.
    """
    return JWTAccessTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_ttl=timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    )


def get_refresh_token_service() -> RefreshTokenService:
    """Создает сервис opaque refresh tokens.

    Returns:
        Сервис генерации, хеширования и проверки refresh tokens.
    """
    return SecureRefreshTokenService()


def get_transaction_manager(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TransactionManager:
    """Создает менеджер транзакций для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Менеджер транзакций SQLAlchemy.
    """
    return SQLAlchemyTransactionManager(session)


def get_refresh_token_ttl() -> timedelta:
    """Возвращает время жизни refresh token из настроек.

    Returns:
        Время жизни refresh token.
    """
    return timedelta(days=settings.refresh_token_ttl_days)


def _raise_invalid_access_token_error(exc: Exception | None = None) -> NoReturn:
    if exc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid access token.",
        headers={"WWW-Authenticate": "Bearer"},
    ) from exc


def _extract_bearer_token(authorization: str | None) -> str:
    """Извлекает Bearer token из Authorization header.

    Args:
        authorization: Значение HTTP header Authorization.

    Returns:
        Строка JWT access token.

    Raises:
        HTTPException: Если header отсутствует или не соответствует Bearer-схеме.
    """
    if authorization is None:
        _raise_invalid_access_token_error()

    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        _raise_invalid_access_token_error()

    return token.strip()


def get_register_user_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    credentials: Annotated[
        AuthCredentialsRepository,
        Depends(get_auth_credentials_repository),
    ],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
) -> RegisterUserUseCase:
    """Собирает use case регистрации пользователя.

    Args:
        users: Репозиторий пользователей.
        credentials: Репозиторий учетных данных.
        password_hasher: Сервис хеширования паролей.
        transaction_manager: Менеджер транзакций.

    Returns:
        Use case регистрации пользователя.
    """
    return RegisterUserUseCase(
        users=users,
        credentials=credentials,
        password_hasher=password_hasher,
        transaction_manager=transaction_manager,
    )


def get_authenticate_user_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    credentials: Annotated[
        AuthCredentialsRepository,
        Depends(get_auth_credentials_repository),
    ],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
) -> AuthenticateUserUseCase:
    """Собирает use case аутентификации пользователя.

    Args:
        users: Репозиторий пользователей.
        credentials: Репозиторий учетных данных.
        password_hasher: Сервис проверки паролей.
        transaction_manager: Менеджер транзакций.

    Returns:
        Use case аутентификации пользователя.
    """
    return AuthenticateUserUseCase(
        users=users,
        credentials=credentials,
        password_hasher=password_hasher,
        transaction_manager=transaction_manager,
    )


def get_current_user_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> GetCurrentUserUseCase:
    """Собирает use case получения текущего пользователя.

    Args:
        users: Репозиторий пользователей.

    Returns:
        Use case получения текущего пользователя.
    """
    return GetCurrentUserUseCase(users=users)


async def get_current_user(
    access_tokens: Annotated[
        AccessTokenService,
        Depends(get_access_token_service),
    ],
    get_current_user_use_case: Annotated[
        GetCurrentUserUseCase,
        Depends(get_current_user_use_case),
    ],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    """Возвращает текущего пользователя по JWT access token.

    Args:
        authorization: Значение HTTP header Authorization.
        access_tokens: Сервис проверки JWT access tokens.
        get_current_user_use_case: Use case получения текущего пользователя.

    Returns:
        Доменная сущность текущего пользователя.

    Raises:
        HTTPException: Если access token невалиден, пользователь не найден
            или пользователь заблокирован.
    """
    token = _extract_bearer_token(authorization)

    try:
        payload = access_tokens.decode_access_token(token)
        return await get_current_user_use_case.execute(user_id=payload.user_id)
    except (
        InvalidAccessTokenError,
        ExpiredAccessTokenError,
        UnsupportedTokenTypeError,
        CurrentUserNotFoundError,
    ) as exc:
        _raise_invalid_access_token_error(exc)
    except CurrentUserBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user is blocked.",
        ) from exc


def get_issue_token_pair_use_case(
    access_tokens: Annotated[AccessTokenService, Depends(get_access_token_service)],
    refresh_tokens: Annotated[
        RefreshTokenService,
        Depends(get_refresh_token_service),
    ],
    sessions: Annotated[AuthSessionRepository, Depends(get_auth_session_repository)],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
    refresh_token_ttl: Annotated[timedelta, Depends(get_refresh_token_ttl)],
) -> IssueTokenPairUseCase:
    """Собирает use case выпуска пары токенов.

    Args:
        access_tokens: Сервис access tokens.
        refresh_tokens: Сервис refresh tokens.
        sessions: Репозиторий refresh-сессий.
        transaction_manager: Менеджер транзакций.
        refresh_token_ttl: Время жизни refresh token.

    Returns:
        Use case выпуска пары токенов.
    """
    return IssueTokenPairUseCase(
        access_tokens=access_tokens,
        refresh_tokens=refresh_tokens,
        sessions=sessions,
        transaction_manager=transaction_manager,
        refresh_token_ttl=refresh_token_ttl,
    )


def get_refresh_token_pair_use_case(
    access_tokens: Annotated[AccessTokenService, Depends(get_access_token_service)],
    refresh_tokens: Annotated[
        RefreshTokenService,
        Depends(get_refresh_token_service),
    ],
    sessions: Annotated[AuthSessionRepository, Depends(get_auth_session_repository)],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
    refresh_token_ttl: Annotated[timedelta, Depends(get_refresh_token_ttl)],
) -> RefreshTokenPairUseCase:
    """Собирает use case обновления пары токенов.

    Args:
        access_tokens: Сервис access tokens.
        refresh_tokens: Сервис refresh tokens.
        sessions: Репозиторий refresh-сессий.
        transaction_manager: Менеджер транзакций.
        refresh_token_ttl: Время жизни нового refresh token.

    Returns:
        Use case обновления пары токенов.
    """
    return RefreshTokenPairUseCase(
        access_tokens=access_tokens,
        refresh_tokens=refresh_tokens,
        sessions=sessions,
        transaction_manager=transaction_manager,
        refresh_token_ttl=refresh_token_ttl,
    )


def get_revoke_refresh_session_use_case(
    refresh_tokens: Annotated[
        RefreshTokenService,
        Depends(get_refresh_token_service),
    ],
    sessions: Annotated[AuthSessionRepository, Depends(get_auth_session_repository)],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
) -> RevokeRefreshSessionUseCase:
    """Собирает use case отзыва refresh-сессии.

    Args:
        refresh_tokens: Сервис refresh tokens.
        sessions: Репозиторий refresh-сессий.
        transaction_manager: Менеджер транзакций.

    Returns:
        Use case отзыва refresh-сессии.
    """
    return RevokeRefreshSessionUseCase(
        refresh_tokens=refresh_tokens,
        sessions=sessions,
        transaction_manager=transaction_manager,
    )
