"""Доменные исключения модуля outbox."""


class OutboxDomainError(Exception):
    """Базовое исключение домена outbox."""


class InvalidOutboxEventError(OutboxDomainError):
    """Сообщает, что outbox event нарушает доменные инварианты."""


class OutboxEventAlreadyPublishedError(OutboxDomainError):
    """Сообщает, что outbox event уже был опубликован."""


class OutboxEventNotFoundError(OutboxDomainError):
    """Сообщает, что outbox event не найден."""
