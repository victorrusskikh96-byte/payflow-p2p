"""Unit-тесты доменных объектов модуля кошельков."""

from uuid import uuid4

import pytest

from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    InsufficientFundsError,
    InvalidBalanceAmountError,
    InvalidBalanceUpdateError,
    InvalidWalletCurrencyError,
    Wallet,
    WalletStatus,
)


def test_wallet_is_created_with_valid_currency() -> None:
    """Проверяет создание кошелька с валидной валютой."""
    wallet = Wallet(user_id=uuid4(), currency="USD")

    assert wallet.currency == "USD"


def test_wallet_currency_is_normalized() -> None:
    """Проверяет нормализацию валюты при создании кошелька."""
    wallet = Wallet(user_id=uuid4(), currency="  usd  ")

    assert wallet.currency == "USD"


@pytest.mark.parametrize("currency", ["", "   "])
def test_empty_wallet_currency_is_forbidden(currency: str) -> None:
    """Проверяет запрет пустой валюты кошелька.

    Args:
        currency: Пустой или пробельный код валюты из параметров теста.
    """
    with pytest.raises(InvalidWalletCurrencyError):
        Wallet(user_id=uuid4(), currency=currency)


def test_wallet_status_is_active_by_default() -> None:
    """Проверяет статус ACTIVE по умолчанию."""
    wallet = Wallet(user_id=uuid4(), currency="USD")

    assert wallet.status is WalletStatus.ACTIVE


@pytest.mark.parametrize(
    "status",
    [
        WalletStatus.BLOCKED,
        WalletStatus.CLOSED,
    ],
)
def test_wallet_can_be_created_with_non_default_status(status: WalletStatus) -> None:
    """Проверяет создание кошелька с нестандартным статусом.

    Args:
        status: Статус кошелька из параметров теста.
    """
    wallet = Wallet(user_id=uuid4(), currency="USD", status=status)

    assert wallet.status is status


def test_balance_projection_is_created_with_zero_amounts() -> None:
    """Проверяет стартовые нулевые значения проекции баланса."""
    balance = BalanceProjection(wallet_id=uuid4(), currency="USD")

    assert balance.available_amount_minor == 0
    assert balance.locked_amount_minor == 0


def test_negative_available_amount_minor_is_forbidden() -> None:
    """Проверяет запрет отрицательной доступной суммы."""
    with pytest.raises(InvalidBalanceAmountError):
        BalanceProjection(
            wallet_id=uuid4(),
            currency="USD",
            available_amount_minor=-1,
        )


def test_negative_locked_amount_minor_is_forbidden() -> None:
    """Проверяет запрет отрицательной заблокированной суммы."""
    with pytest.raises(InvalidBalanceAmountError):
        BalanceProjection(
            wallet_id=uuid4(),
            currency="USD",
            locked_amount_minor=-1,
        )


def test_balance_projection_increases_available_amount() -> None:
    """Проверяет увеличение доступного баланса."""
    balance = BalanceProjection(wallet_id=uuid4(), currency="USD")

    balance.increase_available_amount(100)

    assert balance.available_amount_minor == 100
    assert balance.locked_amount_minor == 0


def test_balance_projection_decreases_available_amount() -> None:
    """Проверяет уменьшение доступного баланса при достаточной сумме."""
    balance = BalanceProjection(
        wallet_id=uuid4(),
        currency="USD",
        available_amount_minor=100,
    )

    balance.decrease_available_amount(40)

    assert balance.available_amount_minor == 60


def test_balance_projection_rejects_decrease_below_zero() -> None:
    """Проверяет запрет уменьшения доступного баланса ниже нуля."""
    balance = BalanceProjection(
        wallet_id=uuid4(),
        currency="USD",
        available_amount_minor=30,
    )

    with pytest.raises(InsufficientFundsError):
        balance.decrease_available_amount(31)

    assert balance.available_amount_minor == 30


def test_balance_projection_rejects_non_positive_update_amount() -> None:
    """Проверяет запрет неположительной суммы обновления."""
    balance = BalanceProjection(wallet_id=uuid4(), currency="USD")

    with pytest.raises(InvalidBalanceUpdateError):
        balance.increase_available_amount(0)


def test_balance_projection_checks_available_amount_sufficiency() -> None:
    """Проверяет оценку достаточности доступного баланса."""
    balance = BalanceProjection(
        wallet_id=uuid4(),
        currency="USD",
        available_amount_minor=100,
    )

    assert balance.has_sufficient_available_balance(100)
    assert not balance.has_sufficient_available_balance(101)


def test_balance_projection_validation_rejects_negative_locked_amount() -> None:
    """Проверяет валидацию отрицательной заблокированной суммы."""
    balance = BalanceProjection(wallet_id=uuid4(), currency="USD")
    balance.locked_amount_minor = -1

    with pytest.raises(InvalidBalanceUpdateError):
        balance.validate()
