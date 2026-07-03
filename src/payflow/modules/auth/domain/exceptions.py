"""Доменные исключения модуля аутентификации."""


class AuthDomainError(Exception):
    """Базовое исключение домена аутентификации."""


class InvalidCredentialsError(AuthDomainError):
    """Сообщает, что учетные данные не подходят для входа."""


class WeakPasswordError(AuthDomainError):
    """Сообщает, что пароль не соответствует политике безопасности."""


class EmailAlreadyRegisteredError(AuthDomainError):
    """Сообщает, что email уже используется для регистрации."""


class CredentialsAlreadyExistError(AuthDomainError):
    """Сообщает, что учетные данные для пользователя уже существуют."""


class CredentialsNotFoundError(AuthDomainError):
    """Сообщает, что учетные данные не найдены."""
