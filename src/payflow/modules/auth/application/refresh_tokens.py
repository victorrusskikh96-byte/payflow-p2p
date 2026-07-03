"""Контракты сервиса refresh tokens для application-слоя."""

from typing import Protocol


class RefreshTokenService(Protocol):
    """Определяет контракт генерации и проверки opaque refresh tokens."""

    def generate_refresh_token(self) -> str:
        """Создает raw refresh token.

        Returns:
            Криптографически случайный opaque refresh token.
        """

    def hash_refresh_token(self, raw_token: str) -> str:
        """Создает хеш refresh token для хранения.

        Args:
            raw_token: Raw refresh token, который нельзя хранить в базе данных.

        Returns:
            Хеш refresh token.
        """

    def verify_refresh_token(self, raw_token: str, token_hash: str) -> bool:
        """Проверяет raw refresh token против сохраненного хеша.

        Args:
            raw_token: Raw refresh token, полученный от пользователя.
            token_hash: Хеш refresh token из хранилища.

        Returns:
            True, если raw refresh token соответствует хешу.
        """
