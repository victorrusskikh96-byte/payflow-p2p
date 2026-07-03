"""Unit-тесты JWT-сервиса access tokens."""

from datetime import timedelta
from uuid import uuid4

import pytest

from payflow.modules.auth.domain import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
)
from payflow.modules.auth.infrastructure import JWTAccessTokenService


def build_access_token_service(
    *,
    secret_key: str = "unit-test-secret-key-with-32-bytes",
    access_token_ttl: timedelta = timedelta(minutes=15),
) -> JWTAccessTokenService:
    """Создает JWT-сервис access tokens для unit-тестов.

    Args:
        secret_key: Секретный ключ для подписи тестовых токенов.
        access_token_ttl: Время жизни тестового access token.

    Returns:
        Настроенный JWT-сервис access tokens.
    """
    return JWTAccessTokenService(
        secret_key=secret_key,
        algorithm="HS256",
        access_token_ttl=access_token_ttl,
    )


def test_access_token_is_created() -> None:
    """Проверяет создание access token."""
    service = build_access_token_service()

    token = service.create_access_token(uuid4())

    assert isinstance(token, str)


def test_access_token_is_not_empty() -> None:
    """Проверяет, что созданный access token не пустой."""
    service = build_access_token_service()

    token = service.create_access_token(uuid4())

    assert token != ""


def test_access_token_can_be_decoded() -> None:
    """Проверяет, что созданный access token можно декодировать."""
    user_id = uuid4()
    service = build_access_token_service()
    token = service.create_access_token(user_id)

    payload = service.decode_access_token(token)

    assert payload.user_id == user_id


def test_decoded_access_token_payload_contains_user_id() -> None:
    """Проверяет наличие user_id в payload access token."""
    user_id = uuid4()
    service = build_access_token_service()
    token = service.create_access_token(user_id)

    payload = service.decode_access_token(token)

    assert payload.user_id == user_id


def test_expired_access_token_is_rejected() -> None:
    """Проверяет отказ для access token с истекшим сроком действия."""
    service = build_access_token_service(access_token_ttl=timedelta(minutes=-1))
    token = service.create_access_token(uuid4())

    with pytest.raises(ExpiredAccessTokenError):
        service.decode_access_token(token)


def test_invalid_access_token_is_rejected() -> None:
    """Проверяет отказ для поврежденного access token."""
    service = build_access_token_service()

    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token("not-a-valid-token")


def test_access_token_with_wrong_signature_is_rejected() -> None:
    """Проверяет отказ для access token с неверной подписью."""
    issuer = build_access_token_service(
        secret_key="issuer-secret-key-with-32-bytes!",
    )
    verifier = build_access_token_service(
        secret_key="verifier-secret-key-with-32-bytes",
    )
    token = issuer.create_access_token(uuid4())

    with pytest.raises(InvalidAccessTokenError):
        verifier.decode_access_token(token)
