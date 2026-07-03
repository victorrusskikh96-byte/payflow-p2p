"""Публичные доменные объекты модуля кошельков."""

from payflow.modules.wallets.domain.balance import BalanceProjection
from payflow.modules.wallets.domain.currency import normalize_currency
from payflow.modules.wallets.domain.exceptions import (
    InvalidBalanceAmountError,
    InvalidWalletCurrencyError,
    WalletAlreadyExistsError,
    WalletBlockedError,
    WalletClosedError,
    WalletNotFoundError,
    WalletOwnerUnavailableError,
    WalletsDomainError,
)
from payflow.modules.wallets.domain.wallet import Wallet, WalletStatus

__all__ = [
    "BalanceProjection",
    "InvalidBalanceAmountError",
    "InvalidWalletCurrencyError",
    "Wallet",
    "WalletAlreadyExistsError",
    "WalletBlockedError",
    "WalletClosedError",
    "WalletNotFoundError",
    "WalletOwnerUnavailableError",
    "WalletStatus",
    "WalletsDomainError",
    "normalize_currency",
]
