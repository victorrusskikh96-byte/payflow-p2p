"""Доменные исключения модуля переводов."""


class TransfersDomainError(Exception):
    """Базовое исключение домена переводов."""


class InvalidTransferAmountError(TransfersDomainError):
    """Сообщает, что сумма перевода некорректна."""


class InvalidTransferCurrencyError(TransfersDomainError):
    """Сообщает, что валюта перевода некорректна."""


class SameTransferWalletsError(TransfersDomainError):
    """Сообщает, что кошельки отправителя и получателя совпадают."""


class InvalidTransferStatusError(TransfersDomainError):
    """Сообщает, что переход статуса перевода некорректен."""


class TransferNotFoundError(TransfersDomainError):
    """Сообщает, что перевод не найден."""


class DuplicateTransferOperationError(TransfersDomainError):
    """Сообщает, что перевод с таким operation id уже существует."""
