"""Доменные исключения модуля ledger."""


class LedgerDomainError(Exception):
    """Базовое исключение домена ledger."""


class InvalidLedgerAmountError(LedgerDomainError):
    """Сообщает, что сумма ledger entry некорректна."""


class InvalidLedgerCurrencyError(LedgerDomainError):
    """Сообщает, что валюта ledger entry некорректна."""


class UnbalancedLedgerTransactionError(LedgerDomainError):
    """Сообщает, что ledger transaction не сбалансирована."""


class MixedLedgerCurrenciesError(LedgerDomainError):
    """Сообщает, что ledger transaction содержит разные валюты."""


class InvalidLedgerEntriesError(LedgerDomainError):
    """Сообщает, что набор ledger entries некорректен."""
