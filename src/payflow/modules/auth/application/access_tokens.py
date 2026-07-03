"""Контракты сервиса access tokens для application-слоя."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessTokenPayload:
    """Описывает проверенные данные access token."""

    user_id: UUID
    expires_at: datetime


class AccessTokenService(Protocol):
    """Определяет контракт выпуска и проверки access tokens."""

    def create_access_token(self, user_id: UUID) -> str:
        """Создает access token для пользователя.

        Args:
            user_id: Идентификатор пользователя-владельца токена.

        Returns:
            Строка с подписанным access token.
        """

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        """Декодирует и валидирует access token.

        Args:
            token: Строка с access token.

        Returns:
            Проверенный payload с идентификатором пользователя и сроком действия.

        Raises:
            InvalidAccessTokenError: Если токен поврежден или подписан неверно.
            ExpiredAccessTokenError: Если срок действия токена истек.
            UnsupportedTokenTypeError: Если токен имеет неподдерживаемый тип.
        """
