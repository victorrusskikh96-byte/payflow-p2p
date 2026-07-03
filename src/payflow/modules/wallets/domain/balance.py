"""Доменная проекция баланса кошелька."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from payflow.modules.wallets.domain.currency import normalize_currency
from payflow.modules.wallets.domain.exceptions import InvalidBalanceAmountError


@dataclass(slots=True, init=False)
class BalanceProjection:
    """Хранит read-модель доступного и заблокированного баланса кошелька."""

    wallet_id: UUID
    available_amount_minor: int
    locked_amount_minor: int
    currency: str
    updated_at: datetime

    def __init__(
        self,
        *,
        wallet_id: UUID,
        currency: str,
        available_amount_minor: int = 0,
        locked_amount_minor: int = 0,
        updated_at: datetime | None = None,
    ) -> None:
        """Создает проекцию баланса кошелька.

        Args:
            wallet_id: Идентификатор кошелька.
            currency: Код валюты баланса.
            available_amount_minor: Доступная сумма в минорных единицах.
            locked_amount_minor: Заблокированная сумма в минорных единицах.
            updated_at: Дата последнего обновления проекции.

        Raises:
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
            InvalidBalanceAmountError: Если доступная или заблокированная сумма
                отрицательная.
        """
        self._validate_amount(available_amount_minor)
        self._validate_amount(locked_amount_minor)

        self.wallet_id = wallet_id
        self.available_amount_minor = available_amount_minor
        self.locked_amount_minor = locked_amount_minor
        self.currency = normalize_currency(currency)
        self.updated_at = updated_at if updated_at is not None else datetime.now(UTC)

    @staticmethod
    def _validate_amount(amount: int) -> None:
        if amount < 0:
            raise InvalidBalanceAmountError("Balance amount cannot be negative.")
