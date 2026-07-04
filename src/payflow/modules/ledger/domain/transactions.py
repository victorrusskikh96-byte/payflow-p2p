"""Доменная модель ledger transaction и правила балансировки."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from payflow.modules.ledger.domain.entries import LedgerEntry, LedgerEntryDirection
from payflow.modules.ledger.domain.exceptions import (
    InvalidLedgerEntriesError,
    MixedLedgerCurrenciesError,
    UnbalancedLedgerTransactionError,
)


class LedgerTransactionStatus(StrEnum):
    """Описывает состояние ledger transaction."""

    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"


class LedgerOperationType(StrEnum):
    """Описывает тип бизнес-операции, породившей ledger transaction."""

    INTERNAL_DEPOSIT = "INTERNAL_DEPOSIT"
    P2P_TRANSFER = "P2P_TRANSFER"
    PAYMENT_DEPOSIT = "PAYMENT_DEPOSIT"
    PAYMENT_WITHDRAWAL = "PAYMENT_WITHDRAWAL"
    REVERSAL = "REVERSAL"


@dataclass(slots=True, init=False)
class LedgerTransaction:
    """Представляет сбалансированную ledger transaction."""

    id: UUID
    operation_id: UUID
    operation_type: LedgerOperationType
    status: LedgerTransactionStatus
    created_at: datetime
    updated_at: datetime
    entries: tuple[LedgerEntry, ...]

    def __init__(
        self,
        *,
        operation_id: UUID,
        operation_type: LedgerOperationType,
        entries: tuple[LedgerEntry, ...],
        id: UUID | None = None,
        status: LedgerTransactionStatus = LedgerTransactionStatus.PENDING,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Создает ledger transaction и проверяет баланс проводок.

        Args:
            operation_id: Идентификатор бизнес-операции.
            operation_type: Тип бизнес-операции.
            entries: Неизменяемые ledger entries этой транзакции.
            id: Идентификатор транзакции, если она уже существует.
            status: Текущий статус транзакции.
            created_at: Дата создания транзакции.
            updated_at: Дата последнего обновления транзакции.

        Raises:
            InvalidLedgerEntriesError: Если entries пустые или относятся к другой
                транзакции.
            MixedLedgerCurrenciesError: Если entries содержат разные валюты.
            UnbalancedLedgerTransactionError: Если сумма DEBIT не равна сумме CREDIT.
        """
        transaction_id = id if id is not None else uuid4()
        self._validate_entries(entries, transaction_id)
        self._validate_single_currency(entries)
        self._validate_balanced(entries)

        now = datetime.now(UTC)

        self.id = transaction_id
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.status = status
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.created_at
        self.entries = entries

    def commit(self) -> None:
        """Переводит ledger transaction в статус COMMITTED.

        Raises:
            InvalidLedgerEntriesError: Если текущий статус не PENDING.
        """
        self._ensure_pending()
        self.status = LedgerTransactionStatus.COMMITTED
        self.updated_at = datetime.now(UTC)

    def fail(self) -> None:
        """Переводит ledger transaction в статус FAILED.

        Raises:
            InvalidLedgerEntriesError: Если текущий статус не PENDING.
        """
        self._ensure_pending()
        self.status = LedgerTransactionStatus.FAILED
        self.updated_at = datetime.now(UTC)

    def is_balanced(self) -> bool:
        """Проверяет, сбалансирована ли ledger transaction.

        Returns:
            True, если сумма DEBIT равна сумме CREDIT в единственной валюте.
        """
        return self._is_single_currency(self.entries) and self._get_debit_total(
            self.entries,
        ) == self._get_credit_total(self.entries)

    def is_committed(self) -> bool:
        """Проверяет, зафиксирована ли ledger transaction.

        Returns:
            True, если статус транзакции равен COMMITTED.
        """
        return self.status is LedgerTransactionStatus.COMMITTED

    def _ensure_pending(self) -> None:
        if self.status is not LedgerTransactionStatus.PENDING:
            raise InvalidLedgerEntriesError("Ledger transaction is not pending.")

    @staticmethod
    def _validate_entries(
        entries: tuple[LedgerEntry, ...],
        transaction_id: UUID,
    ) -> None:
        if not entries:
            raise InvalidLedgerEntriesError(
                "Ledger transaction entries cannot be empty.",
            )

        if any(entry.transaction_id != transaction_id for entry in entries):
            raise InvalidLedgerEntriesError(
                "Ledger transaction entries must reference transaction id.",
            )

    @classmethod
    def _validate_single_currency(cls, entries: tuple[LedgerEntry, ...]) -> None:
        if not cls._is_single_currency(entries):
            raise MixedLedgerCurrenciesError(
                "Ledger transaction cannot mix currencies.",
            )

    @classmethod
    def _validate_balanced(cls, entries: tuple[LedgerEntry, ...]) -> None:
        if cls._get_debit_total(entries) != cls._get_credit_total(entries):
            raise UnbalancedLedgerTransactionError(
                "Ledger transaction debit and credit totals must be equal.",
            )

    @staticmethod
    def _is_single_currency(entries: tuple[LedgerEntry, ...]) -> bool:
        currencies = {entry.currency for entry in entries}
        return len(currencies) == 1

    @staticmethod
    def _get_debit_total(entries: tuple[LedgerEntry, ...]) -> int:
        return sum(
            entry.amount_minor
            for entry in entries
            if entry.direction is LedgerEntryDirection.DEBIT
        )

    @staticmethod
    def _get_credit_total(entries: tuple[LedgerEntry, ...]) -> int:
        return sum(
            entry.amount_minor
            for entry in entries
            if entry.direction is LedgerEntryDirection.CREDIT
        )
