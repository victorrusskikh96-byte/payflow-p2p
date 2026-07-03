"""Мапперы между доменными auth-сущностями и SQLAlchemy-моделями."""

from payflow.modules.auth.domain import AuthCredentials, AuthSession, AuthSessionStatus
from payflow.modules.auth.infrastructure.models import (
    AuthCredentialsModel,
    AuthSessionModel,
)


def auth_credentials_entity_to_model(
    credentials: AuthCredentials,
) -> AuthCredentialsModel:
    """Преобразует доменные учетные данные в ORM-модель.

    Args:
        credentials: Доменная сущность учетных данных.

    Returns:
        SQLAlchemy-модель учетных данных.
    """
    return AuthCredentialsModel(
        id=credentials.id,
        user_id=credentials.user_id,
        password_hash=credentials.password_hash,
        created_at=credentials.created_at,
        updated_at=credentials.updated_at,
    )


def auth_credentials_model_to_entity(
    credentials_model: AuthCredentialsModel,
) -> AuthCredentials:
    """Преобразует ORM-модель учетных данных в доменную сущность.

    Args:
        credentials_model: SQLAlchemy-модель учетных данных.

    Returns:
        Доменная сущность учетных данных.
    """
    return AuthCredentials(
        id=credentials_model.id,
        user_id=credentials_model.user_id,
        password_hash=credentials_model.password_hash,
        created_at=credentials_model.created_at,
        updated_at=credentials_model.updated_at,
    )


def auth_session_entity_to_model(session: AuthSession) -> AuthSessionModel:
    """Преобразует доменную refresh-сессию в ORM-модель.

    Args:
        session: Доменная сущность refresh-сессии.

    Returns:
        SQLAlchemy-модель refresh-сессии.
    """
    return AuthSessionModel(
        id=session.id,
        user_id=session.user_id,
        refresh_token_hash=session.refresh_token_hash,
        status=session.status.value,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        revoked_at=session.revoked_at,
    )


def auth_session_model_to_entity(session_model: AuthSessionModel) -> AuthSession:
    """Преобразует ORM-модель refresh-сессии в доменную сущность.

    Args:
        session_model: SQLAlchemy-модель refresh-сессии.

    Returns:
        Доменная сущность refresh-сессии.
    """
    return AuthSession(
        id=session_model.id,
        user_id=session_model.user_id,
        refresh_token_hash=session_model.refresh_token_hash,
        status=AuthSessionStatus(session_model.status),
        expires_at=session_model.expires_at,
        created_at=session_model.created_at,
        updated_at=session_model.updated_at,
        revoked_at=session_model.revoked_at,
    )
