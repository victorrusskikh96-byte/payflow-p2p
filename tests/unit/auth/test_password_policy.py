"""Unit-тесты доменной политики паролей."""

import pytest

from payflow.modules.auth.domain import WeakPasswordError, validate_password


@pytest.mark.parametrize("password", ["", "   "])
def test_empty_password_is_forbidden(password: str) -> None:
    """Проверяет запрет пустого пароля.

    Args:
        password: Пустой или пробельный пароль из параметров теста.
    """
    with pytest.raises(WeakPasswordError):
        validate_password(password)


def test_short_password_is_forbidden() -> None:
    """Проверяет запрет пароля короче минимальной длины."""
    with pytest.raises(WeakPasswordError):
        validate_password("short")


def test_valid_password_passes_validation() -> None:
    """Проверяет успешную валидацию корректного пароля."""
    validate_password("valid-password")
