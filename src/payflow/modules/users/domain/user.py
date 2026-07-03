"""Доменная модель пользователя и его статусы."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from payflow.modules.users.domain.exceptions import EmptyUserEmailError


class UserStatus(StrEnum):
    """Описывает возможные состояния пользователя в системе."""

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


@dataclass(slots=True, init=False)
class User:
    """Представляет пользователя и гарантирует нормализацию email."""

    id: UUID
    email: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        *,
        email: str,
        id: UUID | None = None,
        status: UserStatus = UserStatus.ACTIVE,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Создает пользователя с нормализованным email и временными метками.

        Args:
            email: Email пользователя.
            id: Идентификатор пользователя, если он уже существует.
            status: Текущий статус пользователя.
            created_at: Дата создания пользователя.
            updated_at: Дата последнего обновления пользователя.

        Raises:
            EmptyUserEmailError: Если email пустой после нормализации.
        """
        now = datetime.now(UTC)

        self.id = id if id is not None else uuid4()
        self.email = self._normalize_email(email)
        self.status = status
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.created_at

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise EmptyUserEmailError("User email cannot be empty.")
        return normalized_email
