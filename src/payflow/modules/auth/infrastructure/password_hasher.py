"""Реализация хеширования паролей через Argon2."""

from argon2 import PasswordHasher as Argon2LibraryPasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from payflow.modules.auth.domain import validate_password


class Argon2PasswordHasher:
    """Хеширует и проверяет пароли с помощью библиотеки Argon2."""

    def __init__(self, hasher: Argon2LibraryPasswordHasher | None = None) -> None:
        """Создает сервис хеширования паролей.

        Args:
            hasher: Преднастроенный экземпляр Argon2-хешера.
        """
        self._hasher = hasher if hasher is not None else Argon2LibraryPasswordHasher()

    def hash_password(self, password: str) -> str:
        """Создает Argon2-хеш для валидного пароля.

        Args:
            password: Пароль в открытом виде.

        Returns:
            Строка с Argon2-хешем.

        Raises:
            WeakPasswordError: Если пароль не проходит доменную политику.
        """
        validate_password(password)
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Проверяет пароль по Argon2-хешу.

        Args:
            password: Пароль в открытом виде.
            password_hash: Сохраненный Argon2-хеш.

        Returns:
            True, если пароль соответствует хешу.
        """
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False
