"""Unit-тесты доменной модели P2P-перевода."""

from uuid import uuid4

import pytest

from payflow.modules.transfers.domain import (
    InvalidTransferAmountError,
    InvalidTransferCurrencyError,
    InvalidTransferStatusError,
    SameTransferWalletsError,
    Transfer,
    TransferStatus,
)


def _make_transfer(
    *,
    amount_minor: int = 100,
    currency: str = "USD",
) -> Transfer:
    """Создает P2P-перевод для unit-тестов.

    Args:
        amount_minor: Сумма перевода в минорных единицах.
        currency: Код валюты перевода.

    Returns:
        P2P-перевод с заданными параметрами.
    """
    return Transfer(
        operation_id=uuid4(),
        sender_user_id=uuid4(),
        sender_wallet_id=uuid4(),
        recipient_wallet_id=uuid4(),
        amount_minor=amount_minor,
        currency=currency,
    )


def test_transfer_is_created_with_pending_status() -> None:
    """Проверяет создание перевода в статусе PENDING."""
    transfer = _make_transfer()

    assert transfer.status is TransferStatus.PENDING


@pytest.mark.parametrize("amount_minor", [0, -1])
def test_non_positive_transfer_amount_is_forbidden(amount_minor: int) -> None:
    """Проверяет запрет неположительной суммы перевода.

    Args:
        amount_minor: Неположительная сумма из параметров теста.
    """
    with pytest.raises(InvalidTransferAmountError):
        _make_transfer(amount_minor=amount_minor)


@pytest.mark.parametrize("currency", ["", "   "])
def test_empty_transfer_currency_is_forbidden(currency: str) -> None:
    """Проверяет запрет пустой валюты перевода.

    Args:
        currency: Пустой или пробельный код валюты из параметров теста.
    """
    with pytest.raises(InvalidTransferCurrencyError):
        _make_transfer(currency=currency)


def test_transfer_currency_is_normalized() -> None:
    """Проверяет нормализацию валюты перевода."""
    transfer = _make_transfer(currency="  usd  ")

    assert transfer.currency == "USD"


def test_same_sender_and_recipient_wallets_are_forbidden() -> None:
    """Проверяет запрет перевода между одним и тем же кошельком."""
    wallet_id = uuid4()

    with pytest.raises(SameTransferWalletsError):
        Transfer(
            operation_id=uuid4(),
            sender_user_id=uuid4(),
            sender_wallet_id=wallet_id,
            recipient_wallet_id=wallet_id,
            amount_minor=100,
            currency="USD",
        )


def test_transfer_can_be_completed() -> None:
    """Проверяет переход перевода в статус COMPLETED."""
    transfer = _make_transfer()
    ledger_transaction_id = uuid4()

    transfer.complete(ledger_transaction_id=ledger_transaction_id)

    assert transfer.status is TransferStatus.COMPLETED
    assert transfer.ledger_transaction_id == ledger_transaction_id
    assert transfer.is_completed()


def test_transfer_can_be_failed() -> None:
    """Проверяет переход перевода в статус FAILED."""
    transfer = _make_transfer()

    transfer.fail()

    assert transfer.status is TransferStatus.FAILED
    assert transfer.failed_at is not None
    assert not transfer.is_completed()


def test_completed_transfer_cannot_be_completed_again() -> None:
    """Проверяет запрет повторного успешного завершения перевода."""
    transfer = _make_transfer()
    transfer.complete(ledger_transaction_id=uuid4())

    with pytest.raises(InvalidTransferStatusError):
        transfer.complete(ledger_transaction_id=uuid4())


def test_failed_transfer_cannot_be_completed() -> None:
    """Проверяет запрет успешного завершения failed-перевода."""
    transfer = _make_transfer()
    transfer.fail()

    with pytest.raises(InvalidTransferStatusError):
        transfer.complete(ledger_transaction_id=uuid4())
