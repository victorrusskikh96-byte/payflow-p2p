"""Доменная модель неизменяемой ledger entry."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from payflow.modules.ledger.domain.exceptions import (
    InvalidLedgerAmountError,
    InvalidLedgerCurrencyError,
)


class LedgerEntryDirection(StrEnum):
    """Описывает направление движения денег в ledger entry."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True, slots=True, init=False)
class LedgerEntry:
    """Представляет неизменяемую запись движения денег по кошельку."""

    id: UUID
    transaction_id: UUID
    wallet_id: UUID
    direction: LedgerEntryDirection
    amount_minor: int
    currency: str
    created_at: datetime

    def __init__(
        self,
        *,
        transaction_id: UUID,
        wallet_id: UUID,
        direction: LedgerEntryDirection,
        amount_minor: int,
        currency: str,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Создает неизменяемую ledger entry.

        Args:
            transaction_id: Идентификатор ledger transaction.
            wallet_id: Идентификатор кошелька, к которому относится запись.
            direction: Направление записи: DEBIT или CREDIT.
            amount_minor: Сумма в минорных единицах.
            currency: Код валюты записи.
            id: Идентификатор записи, если она уже существует.
            created_at: Дата создания записи.

        Raises:
            InvalidLedgerAmountError: Если сумма не больше нуля.
            InvalidLedgerCurrencyError: Если валюта пустая после нормализации.
        """
        self._validate_amount(amount_minor)

        object.__setattr__(self, "id", id if id is not None else uuid4())
        object.__setattr__(self, "transaction_id", transaction_id)
        object.__setattr__(self, "wallet_id", wallet_id)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "amount_minor", amount_minor)
        object.__setattr__(self, "currency", self._normalize_currency(currency))
        object.__setattr__(
            self,
            "created_at",
            created_at if created_at is not None else datetime.now(UTC),
        )

    @staticmethod
    def _validate_amount(amount_minor: int) -> None:
        if amount_minor <= 0:
            raise InvalidLedgerAmountError("Ledger entry amount must be positive.")

    @staticmethod
    def _normalize_currency(currency: str) -> str:
        normalized_currency = currency.strip().upper()
        if not normalized_currency:
            raise InvalidLedgerCurrencyError("Ledger entry currency cannot be empty.")
        return normalized_currency
