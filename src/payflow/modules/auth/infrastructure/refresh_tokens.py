"""Инфраструктурная реализация сервиса opaque refresh tokens."""

import hashlib
import hmac
import secrets


class SecureRefreshTokenService:
    """Создает и проверяет криптографически случайные refresh tokens."""

    def __init__(self, *, token_bytes: int = 64) -> None:
        """Создает сервис refresh tokens.

        Args:
            token_bytes: Количество случайных байтов в raw refresh token.
        """
        self._token_bytes = token_bytes

    def generate_refresh_token(self) -> str:
        """Создает opaque refresh token.

        Returns:
            Криптографически случайный refresh token.
        """
        return secrets.token_urlsafe(self._token_bytes)

    def hash_refresh_token(self, raw_token: str) -> str:
        """Создает SHA-256 хеш refresh token для хранения.

        Args:
            raw_token: Raw refresh token, который нельзя хранить в базе данных.

        Returns:
            Hex-encoded SHA-256 хеш refresh token.
        """
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def verify_refresh_token(self, raw_token: str, token_hash: str) -> bool:
        """Проверяет raw refresh token против сохраненного хеша.

        Args:
            raw_token: Raw refresh token, полученный от пользователя.
            token_hash: Хеш refresh token из хранилища.

        Returns:
            True, если raw refresh token соответствует хешу.
        """
        candidate_hash = self.hash_refresh_token(raw_token)
        return hmac.compare_digest(candidate_hash, token_hash)
