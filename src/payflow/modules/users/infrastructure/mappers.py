"""Мапперы между доменными пользователями и SQLAlchemy-моделями."""

from payflow.modules.users.domain import User, UserStatus
from payflow.modules.users.infrastructure.models import UserModel


def user_entity_to_model(user: User) -> UserModel:
    """Преобразует доменную сущность пользователя в ORM-модель.

    Args:
        user: Доменная сущность пользователя.

    Returns:
        SQLAlchemy-модель пользователя.
    """
    return UserModel(
        id=user.id,
        email=user.email,
        status=user.status.value,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def user_model_to_entity(user_model: UserModel) -> User:
    """Преобразует ORM-модель пользователя в доменную сущность.

    Args:
        user_model: SQLAlchemy-модель пользователя.

    Returns:
        Доменная сущность пользователя.
    """
    return User(
        id=user_model.id,
        email=user_model.email,
        status=UserStatus(user_model.status),
        created_at=user_model.created_at,
        updated_at=user_model.updated_at,
    )
