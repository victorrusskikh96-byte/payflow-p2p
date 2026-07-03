"""Мапперы между доменными учетными данными и SQLAlchemy-моделями."""

from payflow.modules.auth.domain import AuthCredentials
from payflow.modules.auth.infrastructure.models import AuthCredentialsModel


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
