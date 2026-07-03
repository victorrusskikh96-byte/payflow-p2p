"""JWT-реализация сервиса access tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError
from jwt import InvalidTokenError as PyJWTInvalidTokenError

from payflow.modules.auth.application.access_tokens import AccessTokenPayload
from payflow.modules.auth.domain import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
    UnsupportedTokenTypeError,
)

ACCESS_TOKEN_TYPE = "access"
TOKEN_TYPE_CLAIM = "token_type"


class JWTAccessTokenService:
    """Создает и проверяет access tokens в формате JWT."""

    def __init__(
        self,
        *,
        secret_key: str,
        algorithm: str,
        access_token_ttl: timedelta,
    ) -> None:
        """Создает JWT-сервис access tokens.

        Args:
            secret_key: Секретный ключ для подписи и проверки токенов.
            algorithm: Алгоритм подписи JWT.
            access_token_ttl: Время жизни access token.
        """
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_ttl = access_token_ttl

    def create_access_token(self, user_id: UUID) -> str:
        """Создает подписанный JWT access token для пользователя.

        Args:
            user_id: Идентификатор пользователя-владельца токена.

        Returns:
            Строка с подписанным JWT access token.
        """
        issued_at = datetime.now(UTC)
        expires_at = issued_at + self._access_token_ttl
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": expires_at,
            TOKEN_TYPE_CLAIM: ACCESS_TOKEN_TYPE,
        }

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        """Декодирует и валидирует JWT access token.

        Args:
            token: Строка с JWT access token.

        Returns:
            Проверенный payload с идентификатором пользователя и сроком действия.

        Raises:
            InvalidAccessTokenError: Если токен поврежден или подписан неверно.
            ExpiredAccessTokenError: Если срок действия токена истек.
            UnsupportedTokenTypeError: Если токен имеет неподдерживаемый тип.
        """
        if not token.strip():
            raise InvalidAccessTokenError("Invalid access token.")

        try:
            decoded_payload: dict[str, Any] = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["exp", "sub", TOKEN_TYPE_CLAIM]},
            )
        except ExpiredSignatureError as exc:
            raise ExpiredAccessTokenError("Access token has expired.") from exc
        except PyJWTInvalidTokenError as exc:
            raise InvalidAccessTokenError("Invalid access token.") from exc

        return self._build_access_token_payload(decoded_payload)

    def _build_access_token_payload(
        self,
        decoded_payload: dict[str, Any],
    ) -> AccessTokenPayload:
        token_type = decoded_payload.get(TOKEN_TYPE_CLAIM)
        if token_type != ACCESS_TOKEN_TYPE:
            raise UnsupportedTokenTypeError("Unsupported token type.")

        subject = decoded_payload.get("sub")
        if not isinstance(subject, str):
            raise InvalidAccessTokenError("Invalid access token.")

        try:
            user_id = UUID(subject)
        except ValueError as exc:
            raise InvalidAccessTokenError("Invalid access token.") from exc

        return AccessTokenPayload(
            user_id=user_id,
            expires_at=self._extract_expires_at(decoded_payload),
        )

    def _extract_expires_at(self, decoded_payload: dict[str, Any]) -> datetime:
        expires_at = decoded_payload.get("exp")
        if not isinstance(expires_at, int | float):
            raise InvalidAccessTokenError("Invalid access token.")

        return datetime.fromtimestamp(expires_at, UTC)
