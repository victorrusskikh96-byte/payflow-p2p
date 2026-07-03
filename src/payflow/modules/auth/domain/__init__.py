"""Публичные доменные объекты модуля аутентификации."""

from payflow.modules.auth.domain.credentials import AuthCredentials
from payflow.modules.auth.domain.exceptions import (
    AuthDomainError,
    CredentialsAlreadyExistError,
    CredentialsNotFoundError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    WeakPasswordError,
)
from payflow.modules.auth.domain.password_policy import (
    MIN_PASSWORD_LENGTH,
    validate_password,
)

__all__ = [
    "MIN_PASSWORD_LENGTH",
    "AuthCredentials",
    "AuthDomainError",
    "CredentialsAlreadyExistError",
    "CredentialsNotFoundError",
    "EmailAlreadyRegisteredError",
    "InvalidCredentialsError",
    "WeakPasswordError",
    "validate_password",
]
