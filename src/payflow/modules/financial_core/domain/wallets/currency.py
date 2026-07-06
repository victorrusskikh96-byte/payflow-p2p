"""Правила нормализации валюты в домене кошельков."""

from payflow.modules.financial_core.domain.wallets.exceptions import (
    InvalidWalletCurrencyError,
)


def normalize_currency(currency: str) -> str:
    """Нормализует код валюты для доменных объектов кошельков.

    Args:
        currency: Исходный код валюты.

    Returns:
        Код валюты без пробелов по краям и в верхнем регистре.

    Raises:
        InvalidWalletCurrencyError: Если валюта пустая после нормализации.
    """
    normalized_currency = currency.strip().upper()
    if not normalized_currency:
        raise InvalidWalletCurrencyError("Wallet currency cannot be empty.")
    return normalized_currency
