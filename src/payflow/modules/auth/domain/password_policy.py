"""Правила доменной валидации паролей."""

from payflow.modules.auth.domain.exceptions import WeakPasswordError

MIN_PASSWORD_LENGTH = 8


def validate_password(password: str) -> None:
    """Проверяет пароль на соответствие минимальной политике безопасности.

    Args:
        password: Пароль для проверки.

    Raises:
        WeakPasswordError: Если пароль пустой или короче минимальной длины.
    """
    normalized_password = password.strip()

    if not normalized_password:
        raise WeakPasswordError("Password cannot be empty.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
