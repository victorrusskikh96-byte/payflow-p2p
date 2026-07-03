"""Доменная модель refresh-сессии аутентификации."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class AuthSessionStatus(StrEnum):
    """Описывает возможные статусы refresh-сессии."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


@dataclass(slots=True, init=False)
class AuthSession:
    """Представляет refresh-сессию пользователя."""

    id: UUID
    user_id: UUID
    refresh_token_hash: str
    status: AuthSessionStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None

    def __init__(
        self,
        *,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        id: UUID | None = None,
        status: AuthSessionStatus = AuthSessionStatus.ACTIVE,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        revoked_at: datetime | None = None,
    ) -> None:
        """Создает refresh-сессию пользователя.

        Args:
            user_id: Идентификатор пользователя-владельца сессии.
            refresh_token_hash: Хеш refresh token.
            expires_at: Дата истечения refresh-сессии.
            id: Идентификатор refresh-сессии.
            status: Текущий статус refresh-сессии.
            created_at: Дата создания refresh-сессии.
            updated_at: Дата последнего изменения refresh-сессии.
            revoked_at: Дата отзыва refresh-сессии.
        """
        now = datetime.now(UTC)

        self.id = id if id is not None else uuid4()
        self.user_id = user_id
        self.refresh_token_hash = refresh_token_hash
        self.status = status
        self.expires_at = expires_at
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.created_at
        self.revoked_at = revoked_at

    def is_active(self, at: datetime | None = None) -> bool:
        """Проверяет, является ли refresh-сессия активной.

        Args:
            at: Момент времени для проверки. Если не передан,
                используется текущее время.

        Returns:
            True, если сессия имеет статус ACTIVE и срок действия еще не истек.
        """
        checked_at = at if at is not None else datetime.now(UTC)
        return self.status is AuthSessionStatus.ACTIVE and self.expires_at > checked_at

    def revoke(self, at: datetime | None = None) -> None:
        """Отзывает refresh-сессию.

        Args:
            at: Момент отзыва. Если не передан, используется текущее время.
        """
        if self.status is AuthSessionStatus.REVOKED:
            return

        revoked_at = at if at is not None else datetime.now(UTC)
        self.status = AuthSessionStatus.REVOKED
        self.revoked_at = revoked_at
        self.updated_at = revoked_at
