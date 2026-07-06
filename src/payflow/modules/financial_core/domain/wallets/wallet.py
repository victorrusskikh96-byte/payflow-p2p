"""Доменная модель кошелька пользователя."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from payflow.modules.financial_core.domain.wallets.currency import normalize_currency


class WalletStatus(StrEnum):
    """Описывает возможные состояния кошелька."""

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"


@dataclass(slots=True, init=False)
class Wallet:
    """Представляет пользовательский кошелек в заданной валюте."""

    id: UUID
    user_id: UUID
    currency: str
    status: WalletStatus
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        *,
        user_id: UUID,
        currency: str,
        id: UUID | None = None,
        status: WalletStatus = WalletStatus.ACTIVE,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Создает кошелек пользователя с нормализованной валютой.

        Args:
            user_id: Идентификатор пользователя-владельца кошелька.
            currency: Код валюты кошелька.
            id: Идентификатор кошелька, если он уже существует.
            status: Текущий статус кошелька.
            created_at: Дата создания кошелька.
            updated_at: Дата последнего обновления кошелька.

        Raises:
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """
        now = datetime.now(UTC)

        self.id = id if id is not None else uuid4()
        self.user_id = user_id
        self.currency = normalize_currency(currency)
        self.status = status
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.created_at
