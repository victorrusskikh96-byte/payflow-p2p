"""Доменная проекция баланса кошелька."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from payflow.modules.wallets.domain.currency import normalize_currency
from payflow.modules.wallets.domain.exceptions import (
    InsufficientFundsError,
    InvalidBalanceAmountError,
    InvalidBalanceUpdateError,
)


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

    def increase_available_amount(self, amount_minor: int) -> None:
        """Увеличивает доступный баланс в минорных единицах.

        Args:
            amount_minor: Сумма увеличения в минорных единицах.

        Raises:
            InvalidBalanceUpdateError: Если сумма увеличения не положительная или
                текущее состояние проекции некорректно.
        """
        self.validate()
        self._validate_positive_update_amount(amount_minor)
        self.available_amount_minor += amount_minor
        self.updated_at = datetime.now(UTC)

    def decrease_available_amount(self, amount_minor: int) -> None:
        """Уменьшает доступный баланс в минорных единицах.

        Args:
            amount_minor: Сумма уменьшения в минорных единицах.

        Raises:
            InvalidBalanceUpdateError: Если сумма уменьшения не положительная или
                текущее состояние проекции некорректно.
            InsufficientFundsError: Если доступного баланса недостаточно.
        """
        self.validate()
        self._validate_positive_update_amount(amount_minor)
        if not self.has_sufficient_available_balance(amount_minor):
            raise InsufficientFundsError("Available balance is insufficient.")

        self.available_amount_minor -= amount_minor
        self.updated_at = datetime.now(UTC)

    def has_sufficient_available_balance(self, amount_minor: int) -> bool:
        """Проверяет достаточность доступного баланса.

        Args:
            amount_minor: Проверяемая сумма в минорных единицах.

        Returns:
            True, если доступного баланса достаточно.

        Raises:
            InvalidBalanceUpdateError: Если проверяемая сумма отрицательная или
                текущее состояние проекции некорректно.
        """
        self.validate()
        if amount_minor < 0:
            raise InvalidBalanceUpdateError("Balance check amount cannot be negative.")
        return self.available_amount_minor >= amount_minor

    def validate(self) -> None:
        """Проверяет инварианты проекции баланса.

        Raises:
            InvalidBalanceUpdateError: Если доступная или заблокированная сумма
                отрицательная.
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """
        if self.available_amount_minor < 0:
            raise InvalidBalanceUpdateError("Available balance cannot be negative.")
        if self.locked_amount_minor < 0:
            raise InvalidBalanceUpdateError("Locked balance cannot be negative.")
        self.currency = normalize_currency(self.currency)

    @staticmethod
    def _validate_amount(amount: int) -> None:
        if amount < 0:
            raise InvalidBalanceAmountError("Balance amount cannot be negative.")

    @staticmethod
    def _validate_positive_update_amount(amount_minor: int) -> None:
        if amount_minor <= 0:
            raise InvalidBalanceUpdateError("Balance update amount must be positive.")
