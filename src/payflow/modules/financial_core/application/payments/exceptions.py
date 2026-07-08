"""Application-исключения модуля платежных операций."""


class PaymentsApplicationError(Exception):
    """Базовое исключение application layer модуля payments."""


class DuplicateInternalDepositOperationError(PaymentsApplicationError):
    """Сообщает, что internal deposit с таким operation_id уже существует."""


class InsufficientSourceFundsError(PaymentsApplicationError):
    """Сообщает, что funding wallet не имеет достаточного доступного баланса."""


class InternalDepositWalletUnavailableError(PaymentsApplicationError):
    """Сообщает, что кошелек недоступен для internal deposit."""


class InvalidInternalDepositAmountError(PaymentsApplicationError):
    """Сообщает, что сумма internal deposit некорректна."""


class SourceWalletEqualsTargetWalletError(PaymentsApplicationError):
    """Сообщает, что source и target wallets совпадают."""


class WalletCurrencyMismatchError(PaymentsApplicationError):
    """Сообщает, что валюты кошельков или команды не совпадают."""


class InternalDepositLedgerCreationFailedError(PaymentsApplicationError):
    """Сообщает, что ledger transaction internal deposit не удалось сохранить."""


class InternalDepositBalanceUpdateFailedError(PaymentsApplicationError):
    """Сообщает, что balance projection internal deposit не удалось обновить."""


class InternalDepositOutboxEventCreationFailedError(PaymentsApplicationError):
    """Сообщает, что outbox event internal deposit не удалось сохранить."""
