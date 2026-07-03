"""Доменные исключения модуля пользователей."""


class UsersDomainError(Exception):
    """Базовое исключение домена пользователей."""


class EmptyUserEmailError(UsersDomainError):
    """Сообщает, что email пользователя пустой после нормализации."""
