"""Интерфейс сервиса хеширования паролей."""

from typing import Protocol


class PasswordHasher(Protocol):
    """Определяет контракт хеширования и проверки паролей."""

    def hash_password(self, password: str) -> str:
        """Создает безопасный хеш пароля.

        Args:
            password: Пароль в открытом виде.

        Returns:
            Строка с хешем пароля.

        Raises:
            WeakPasswordError: Если пароль не проходит доменную политику.
        """

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Проверяет соответствие пароля сохраненному хешу.

        Args:
            password: Пароль в открытом виде.
            password_hash: Сохраненный хеш пароля.

        Returns:
            True, если пароль соответствует хешу.
        """
