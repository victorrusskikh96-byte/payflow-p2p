"""Unit-тесты Argon2-хешера паролей."""

from argon2 import PasswordHasher as Argon2LibraryPasswordHasher

from payflow.modules.auth.infrastructure import Argon2PasswordHasher


def build_password_hasher() -> Argon2PasswordHasher:
    """Создает быстрый Argon2-хешер для unit-тестов.

    Returns:
        Настроенный тестовый хешер паролей.
    """
    return Argon2PasswordHasher(
        Argon2LibraryPasswordHasher(
            time_cost=1,
            memory_cost=1024,
            parallelism=1,
            hash_len=16,
            salt_len=16,
        )
    )


def test_password_hasher_creates_hash_different_from_password() -> None:
    """Проверяет, что хеш не совпадает с исходным паролем."""
    password = "valid-password"
    password_hasher = build_password_hasher()

    password_hash = password_hasher.hash_password(password)

    assert password_hash != password


def test_password_hasher_verifies_correct_password() -> None:
    """Проверяет успешную верификацию корректного пароля."""
    password = "valid-password"
    password_hasher = build_password_hasher()
    password_hash = password_hasher.hash_password(password)

    assert password_hasher.verify_password(password, password_hash) is True


def test_password_hasher_rejects_wrong_password() -> None:
    """Проверяет отказ при неверном пароле."""
    password_hasher = build_password_hasher()
    password_hash = password_hasher.hash_password("valid-password")

    assert password_hasher.verify_password("wrong-password", password_hash) is False
