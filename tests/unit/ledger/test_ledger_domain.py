"""Unit-тесты доменных объектов модуля ledger."""

from uuid import UUID, uuid4

import pytest

from payflow.modules.financial_core.domain.ledger import (
    InvalidLedgerAmountError,
    InvalidLedgerCurrencyError,
    InvalidLedgerEntriesError,
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
    LedgerTransactionStatus,
    MixedLedgerCurrenciesError,
    UnbalancedLedgerTransactionError,
)


def _make_entry(
    *,
    transaction_id: UUID,
    direction: LedgerEntryDirection,
    amount_minor: int = 100,
    currency: str = "USD",
) -> LedgerEntry:
    """Создает ledger entry для тестов.

    Args:
        transaction_id: Идентификатор ledger transaction.
        direction: Направление записи.
        amount_minor: Сумма в минорных единицах.
        currency: Код валюты.

    Returns:
        Ledger entry с заданными параметрами.
    """
    return LedgerEntry(
        transaction_id=transaction_id,
        wallet_id=uuid4(),
        direction=direction,
        amount_minor=amount_minor,
        currency=currency,
    )


def _make_transaction(
    *,
    transaction_id: UUID | None = None,
    entries: tuple[LedgerEntry, ...] | None = None,
    status: LedgerTransactionStatus = LedgerTransactionStatus.PENDING,
) -> LedgerTransaction:
    """Создает ledger transaction для тестов.

    Args:
        transaction_id: Идентификатор ledger transaction.
        entries: Ledger entries транзакции.
        status: Начальный статус транзакции.

    Returns:
        Ledger transaction с заданными параметрами.
    """
    resolved_transaction_id = transaction_id if transaction_id is not None else uuid4()
    resolved_entries = entries
    if resolved_entries is None:
        resolved_entries = (
            _make_entry(
                transaction_id=resolved_transaction_id,
                direction=LedgerEntryDirection.DEBIT,
            ),
            _make_entry(
                transaction_id=resolved_transaction_id,
                direction=LedgerEntryDirection.CREDIT,
            ),
        )

    return LedgerTransaction(
        id=resolved_transaction_id,
        operation_id=uuid4(),
        operation_type=LedgerOperationType.P2P_TRANSFER,
        status=status,
        entries=resolved_entries,
    )


def test_ledger_entry_is_created_with_debit_direction() -> None:
    """Проверяет создание ledger entry с направлением DEBIT."""
    entry = _make_entry(transaction_id=uuid4(), direction=LedgerEntryDirection.DEBIT)

    assert entry.direction is LedgerEntryDirection.DEBIT


def test_ledger_entry_is_created_with_credit_direction() -> None:
    """Проверяет создание ledger entry с направлением CREDIT."""
    entry = _make_entry(transaction_id=uuid4(), direction=LedgerEntryDirection.CREDIT)

    assert entry.direction is LedgerEntryDirection.CREDIT


@pytest.mark.parametrize("amount_minor", [0, -1])
def test_non_positive_ledger_entry_amount_is_forbidden(amount_minor: int) -> None:
    """Проверяет запрет неположительной суммы ledger entry.

    Args:
        amount_minor: Неположительная сумма из параметров теста.
    """
    with pytest.raises(InvalidLedgerAmountError):
        _make_entry(
            transaction_id=uuid4(),
            direction=LedgerEntryDirection.DEBIT,
            amount_minor=amount_minor,
        )


@pytest.mark.parametrize("currency", ["", "   "])
def test_empty_ledger_entry_currency_is_forbidden(currency: str) -> None:
    """Проверяет запрет пустой валюты ledger entry.

    Args:
        currency: Пустой или пробельный код валюты из параметров теста.
    """
    with pytest.raises(InvalidLedgerCurrencyError):
        _make_entry(
            transaction_id=uuid4(),
            direction=LedgerEntryDirection.DEBIT,
            currency=currency,
        )


def test_ledger_entry_currency_is_normalized() -> None:
    """Проверяет нормализацию валюты ledger entry."""
    entry = _make_entry(
        transaction_id=uuid4(),
        direction=LedgerEntryDirection.DEBIT,
        currency="  usd  ",
    )

    assert entry.currency == "USD"


def test_transaction_with_equal_debit_and_credit_totals_is_balanced() -> None:
    """Проверяет, что равные DEBIT и CREDIT суммы считаются balanced."""
    transaction = _make_transaction()

    assert transaction.is_balanced()


def test_transaction_with_unequal_debit_and_credit_totals_is_forbidden() -> None:
    """Проверяет запрет ledger transaction с неравными суммами."""
    transaction_id = uuid4()
    entries = (
        _make_entry(
            transaction_id=transaction_id,
            direction=LedgerEntryDirection.DEBIT,
            amount_minor=100,
        ),
        _make_entry(
            transaction_id=transaction_id,
            direction=LedgerEntryDirection.CREDIT,
            amount_minor=90,
        ),
    )

    with pytest.raises(UnbalancedLedgerTransactionError):
        _make_transaction(transaction_id=transaction_id, entries=entries)


def test_transaction_with_mixed_currencies_is_forbidden() -> None:
    """Проверяет запрет ledger transaction с разными валютами."""
    transaction_id = uuid4()
    entries = (
        _make_entry(
            transaction_id=transaction_id,
            direction=LedgerEntryDirection.DEBIT,
            currency="USD",
        ),
        _make_entry(
            transaction_id=transaction_id,
            direction=LedgerEntryDirection.CREDIT,
            currency="EUR",
        ),
    )

    with pytest.raises(MixedLedgerCurrenciesError):
        _make_transaction(transaction_id=transaction_id, entries=entries)


def test_transaction_without_entries_is_forbidden() -> None:
    """Проверяет запрет ledger transaction без entries."""
    with pytest.raises(InvalidLedgerEntriesError):
        _make_transaction(transaction_id=uuid4(), entries=())


def test_transaction_can_be_committed() -> None:
    """Проверяет переход ledger transaction в COMMITTED."""
    transaction = _make_transaction()

    transaction.commit()

    assert transaction.status is LedgerTransactionStatus.COMMITTED
    assert transaction.is_committed()


def test_failed_transaction_is_not_committed() -> None:
    """Проверяет, что FAILED transaction не считается committed."""
    transaction = _make_transaction(status=LedgerTransactionStatus.FAILED)

    assert not transaction.is_committed()
