"""Unit-тесты доменной сущности пользователя."""

import pytest

from payflow.modules.users.domain import EmptyUserEmailError, User, UserStatus


def test_user_is_created_with_valid_email() -> None:
    """Проверяет создание пользователя с валидным email."""
    user = User(email="user@example.com")

    assert user.email == "user@example.com"


def test_user_email_is_normalized() -> None:
    """Проверяет нормализацию email при создании пользователя."""
    user = User(email="  User@Example.COM  ")

    assert user.email == "user@example.com"


@pytest.mark.parametrize("email", ["", "   "])
def test_empty_user_email_is_forbidden(email: str) -> None:
    """Проверяет запрет пустого email пользователя.

    Args:
        email: Пустой или пробельный email из параметров теста.
    """
    with pytest.raises(EmptyUserEmailError):
        User(email=email)


def test_user_status_is_active_by_default() -> None:
    """Проверяет статус ACTIVE по умолчанию."""
    user = User(email="user@example.com")

    assert user.status is UserStatus.ACTIVE


@pytest.mark.parametrize(
    "status",
    [
        UserStatus.BLOCKED,
        UserStatus.PENDING_VERIFICATION,
    ],
)
def test_user_can_be_created_with_non_default_status(status: UserStatus) -> None:
    """Проверяет создание пользователя с нестандартным статусом.

    Args:
        status: Статус пользователя из параметров теста.
    """
    user = User(email="user@example.com", status=status)

    assert user.status is status
