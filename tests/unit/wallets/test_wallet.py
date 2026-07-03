"""Unit-тесты доменных объектов модуля кошельков."""

from uuid import uuid4

import pytest

from payflow.modules.wallets.domain import (
    BalanceProjection,
    InvalidBalanceAmountError,
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
