"""Доменные исключения модуля аутентификации."""


class AuthDomainError(Exception):
    """Базовое исключение домена аутентификации."""


class InvalidCredentialsError(AuthDomainError):
    """Сообщает, что учетные данные не подходят для входа."""


class InvalidAccessTokenError(AuthDomainError):
    """Сообщает, что access token не прошел проверку."""


class ExpiredAccessTokenError(AuthDomainError):
    """Сообщает, что срок действия access token истек."""


class InvalidRefreshTokenError(AuthDomainError):
    """Сообщает, что refresh token или refresh-сессия невалидны."""


class ExpiredRefreshTokenError(AuthDomainError):
    """Сообщает, что срок действия refresh token истек."""


class UnsupportedTokenTypeError(AuthDomainError):
    """Сообщает, что тип токена не поддерживается для операции."""


class CurrentUserNotFoundError(AuthDomainError):
    """Сообщает, что пользователь из access token не найден."""


class CurrentUserBlockedError(AuthDomainError):
    """Сообщает, что пользователь из access token заблокирован."""


class WeakPasswordError(AuthDomainError):
    """Сообщает, что пароль не соответствует политике безопасности."""


class EmailAlreadyRegisteredError(AuthDomainError):
    """Сообщает, что email уже используется для регистрации."""


class CredentialsAlreadyExistError(AuthDomainError):
    """Сообщает, что учетные данные для пользователя уже существуют."""


class CredentialsNotFoundError(AuthDomainError):
    """Сообщает, что учетные данные не найдены."""
