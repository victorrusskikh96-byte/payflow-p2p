"""Доменная модель учетных данных пользователя."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True, init=False)
class AuthCredentials:
    """Хранит хеш пароля, связанный с пользователем."""

    id: UUID
    user_id: UUID
    password_hash: str
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        *,
        user_id: UUID,
        password_hash: str,
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Создает учетные данные пользователя.

        Args:
            user_id: Идентификатор пользователя-владельца.
            password_hash: Хеш пароля пользователя.
            id: Идентификатор записи учетных данных.
            created_at: Дата создания записи.
            updated_at: Дата последнего обновления записи.
        """
        now = datetime.now(UTC)

        self.id = id if id is not None else uuid4()
        self.user_id = user_id
        self.password_hash = password_hash
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.created_at
