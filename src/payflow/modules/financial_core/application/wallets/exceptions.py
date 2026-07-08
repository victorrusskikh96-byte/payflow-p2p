"""Application-исключения модуля кошельков."""


class WalletsApplicationError(Exception):
    """Базовое исключение application layer модуля wallets."""


class WalletCreationFailedError(WalletsApplicationError):
    """Сообщает, что кошелек не удалось сохранить."""


class WalletBalanceProjectionCreationFailedError(WalletsApplicationError):
    """Сообщает, что начальную проекцию баланса не удалось сохранить."""


class WalletOutboxEventCreationFailedError(WalletsApplicationError):
    """Сообщает, что outbox event кошелька не удалось сохранить."""
