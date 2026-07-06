"""Application-исключения модуля P2P-переводов."""


class TransfersApplicationError(Exception):
    """Базовое исключение application layer модуля transfers."""


class SenderWalletNotFoundError(TransfersApplicationError):
    """Сообщает, что кошелек отправителя не найден."""


class RecipientWalletNotFoundError(TransfersApplicationError):
    """Сообщает, что кошелек получателя не найден."""


class TransferWalletOwnershipError(TransfersApplicationError):
    """Сообщает, что кошелек отправителя принадлежит другому пользователю."""


class TransferWalletCurrencyMismatchError(TransfersApplicationError):
    """Сообщает, что валюты кошельков или команды перевода не совпадают."""


class InsufficientTransferFundsError(TransfersApplicationError):
    """Сообщает, что доступного баланса отправителя недостаточно для перевода."""


class InactiveTransferWalletError(TransfersApplicationError):
    """Сообщает, что один из кошельков перевода не активен."""
