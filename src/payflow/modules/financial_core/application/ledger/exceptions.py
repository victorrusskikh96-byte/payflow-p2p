"""Application-исключения модуля ledger."""


class LedgerApplicationError(Exception):
    """Базовое исключение application layer модуля ledger."""


class LedgerTransactionAlreadyExistsError(LedgerApplicationError):
    """Сообщает, что ledger transaction для operation_id уже существует."""


class LedgerTransactionCreationFailedError(LedgerApplicationError):
    """Сообщает, что ledger transaction не удалось сохранить."""
