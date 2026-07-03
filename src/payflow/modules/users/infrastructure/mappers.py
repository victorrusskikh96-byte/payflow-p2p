from payflow.modules.users.domain import User, UserStatus
from payflow.modules.users.infrastructure.models import UserModel


def user_entity_to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email,
        status=user.status.value,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def user_model_to_entity(user_model: UserModel) -> User:
    return User(
        id=user_model.id,
        email=user_model.email,
        status=UserStatus(user_model.status),
        created_at=user_model.created_at,
        updated_at=user_model.updated_at,
    )
