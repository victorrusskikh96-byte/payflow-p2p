"""Доменные исключения модуля кошельков."""


class WalletsDomainError(Exception):
    """Базовое исключение домена кошельков."""


class InvalidWalletCurrencyError(WalletsDomainError):
    """Сообщает, что валюта кошелька некорректна."""


class InvalidBalanceAmountError(WalletsDomainError):
    """Сообщает, что сумма в проекции баланса некорректна."""


class WalletBlockedError(WalletsDomainError):
    """Сообщает, что операция невозможна для заблокированного кошелька."""


class WalletClosedError(WalletsDomainError):
    """Сообщает, что операция невозможна для закрытого кошелька."""


class WalletNotFoundError(WalletsDomainError):
    """Сообщает, что кошелек не найден."""


class WalletAlreadyExistsError(WalletsDomainError):
    """Сообщает, что кошелек уже существует."""


class WalletOwnerUnavailableError(WalletsDomainError):
    """Сообщает, что владелец кошелька не найден или заблокирован."""
