"""Unit-тесты доменной сущности refresh-сессии."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from payflow.modules.auth.domain import AuthSession, AuthSessionStatus


def test_auth_session_is_active_with_active_status_and_future_expiration() -> None:
    """Проверяет активность сессии со статусом ACTIVE и будущим сроком."""
    checked_at = datetime(2026, 7, 3, tzinfo=UTC)
    session = AuthSession(
        user_id=uuid4(),
        refresh_token_hash="refresh-token-hash",
        expires_at=checked_at + timedelta(days=1),
    )

    assert session.is_active(checked_at)


def test_auth_session_is_not_active_when_revoked() -> None:
    """Проверяет неактивность отозванной сессии."""
    checked_at = datetime(2026, 7, 3, tzinfo=UTC)
    session = AuthSession(
        user_id=uuid4(),
        refresh_token_hash="refresh-token-hash",
        status=AuthSessionStatus.REVOKED,
        expires_at=checked_at + timedelta(days=1),
        revoked_at=checked_at,
    )

    assert not session.is_active(checked_at)


def test_auth_session_is_not_active_when_expired() -> None:
    """Проверяет неактивность сессии с истекшим сроком."""
    checked_at = datetime(2026, 7, 3, tzinfo=UTC)
    session = AuthSession(
        user_id=uuid4(),
        refresh_token_hash="refresh-token-hash",
        expires_at=checked_at - timedelta(seconds=1),
    )

    assert not session.is_active(checked_at)


def test_auth_session_is_not_active_with_expired_status() -> None:
    """Проверяет неактивность сессии со статусом EXPIRED."""
    checked_at = datetime(2026, 7, 3, tzinfo=UTC)
    session = AuthSession(
        user_id=uuid4(),
        refresh_token_hash="refresh-token-hash",
        status=AuthSessionStatus.EXPIRED,
        expires_at=checked_at + timedelta(days=1),
    )

    assert not session.is_active(checked_at)


def test_auth_session_can_be_revoked() -> None:
    """Проверяет отзыв refresh-сессии."""
    revoked_at = datetime(2026, 7, 3, tzinfo=UTC)
    session = AuthSession(
        user_id=uuid4(),
        refresh_token_hash="refresh-token-hash",
        expires_at=revoked_at + timedelta(days=1),
    )

    session.revoke(revoked_at)

    assert session.status is AuthSessionStatus.REVOKED
    assert session.revoked_at == revoked_at
    assert session.updated_at == revoked_at
    assert not session.is_active(revoked_at)
