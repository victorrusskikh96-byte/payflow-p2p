"""Публичные доменные объекты модуля кошельков."""

from payflow.modules.wallets.domain.balance import BalanceProjection
from payflow.modules.wallets.domain.currency import normalize_currency
from payflow.modules.wallets.domain.exceptions import (
    InsufficientFundsError,
    InvalidBalanceAmountError,
    InvalidBalanceUpdateError,
    InvalidWalletCurrencyError,
    WalletAlreadyExistsError,
    WalletBalanceNotFoundError,
    WalletBlockedError,
    WalletClosedError,
    WalletNotFoundError,
    WalletOwnerUnavailableError,
    WalletsDomainError,
)
from payflow.modules.wallets.domain.wallet import Wallet, WalletStatus

__all__ = [
    "BalanceProjection",
    "InsufficientFundsError",
    "InvalidBalanceAmountError",
    "InvalidBalanceUpdateError",
    "InvalidWalletCurrencyError",
    "Wallet",
    "WalletAlreadyExistsError",
    "WalletBalanceNotFoundError",
    "WalletBlockedError",
    "WalletClosedError",
    "WalletNotFoundError",
    "WalletOwnerUnavailableError",
    "WalletStatus",
    "WalletsDomainError",
    "normalize_currency",
]
