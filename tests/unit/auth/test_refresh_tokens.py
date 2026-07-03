"""Unit-тесты сервиса opaque refresh tokens."""

from payflow.modules.auth.infrastructure import SecureRefreshTokenService


def test_refresh_token_is_generated() -> None:
    """Проверяет генерацию refresh token."""
    service = SecureRefreshTokenService()

    token = service.generate_refresh_token()

    assert isinstance(token, str)
    assert token != ""


def test_generated_refresh_tokens_are_random() -> None:
    """Проверяет, что refresh tokens генерируются случайными."""
    service = SecureRefreshTokenService()

    first_token = service.generate_refresh_token()
    second_token = service.generate_refresh_token()

    assert first_token != second_token


def test_refresh_token_hash_does_not_store_raw_token() -> None:
    """Проверяет, что hash refresh token не равен raw token."""
    service = SecureRefreshTokenService()
    token = service.generate_refresh_token()

    token_hash = service.hash_refresh_token(token)

    assert token_hash != token


def test_refresh_token_is_verified_against_hash() -> None:
    """Проверяет успешную проверку refresh token по hash."""
    service = SecureRefreshTokenService()
    token = service.generate_refresh_token()
    token_hash = service.hash_refresh_token(token)

    assert service.verify_refresh_token(token, token_hash)


def test_wrong_refresh_token_is_rejected() -> None:
    """Проверяет отказ для refresh token, который не соответствует hash."""
    service = SecureRefreshTokenService()
    token_hash = service.hash_refresh_token("valid-refresh-token")

    assert not service.verify_refresh_token("wrong-refresh-token", token_hash)
