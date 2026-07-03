"""Unit-тесты use cases выдачи и обновления token pair."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from payflow.modules.auth.application import (
    AccessTokenPayload,
    IssueTokenPairUseCase,
    RefreshTokenPairUseCase,
    RevokeRefreshSessionUseCase,
)
from payflow.modules.auth.domain import (
    AuthSession,
    ExpiredRefreshTokenError,
    InvalidRefreshTokenError,
)


class FakeAccessTokenService:
    """Тестовый сервис JWT access tokens."""

    def __init__(self) -> None:
        """Создает сервис с пустым хранилищем payload."""
        self._counter = 0
        self._payloads: dict[str, AccessTokenPayload] = {}

    def create_access_token(self, user_id: UUID) -> str:
        """Создает детерминированный access token.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Тестовый access token.
        """
        self._counter += 1
        token = f"access-{self._counter}"
        self._payloads[token] = AccessTokenPayload(
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        return token

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        """Возвращает payload тестового access token.

        Args:
            token: Тестовый access token.

        Returns:
            Payload access token.

        Raises:
            KeyError: Если token не выпускался сервисом.
        """
        return self._payloads[token]


class FakeRefreshTokenService:
    """Тестовый сервис opaque refresh tokens."""

    def __init__(self) -> None:
        """Создает сервис с детерминированным счетчиком tokens."""
        self._counter = 0

    def generate_refresh_token(self) -> str:
        """Создает детерминированный refresh token.

        Returns:
            Тестовый raw refresh token.
        """
        self._counter += 1
        return f"refresh-{self._counter}"

    def hash_refresh_token(self, raw_token: str) -> str:
        """Создает тестовый hash refresh token.

        Args:
            raw_token: Raw refresh token.

        Returns:
            Тестовый hash refresh token.
        """
        return f"hashed:{raw_token}"

    def verify_refresh_token(self, raw_token: str, token_hash: str) -> bool:
        """Проверяет raw refresh token против тестового hash.

        Args:
            raw_token: Raw refresh token.
            token_hash: Hash refresh token.

        Returns:
            True, если raw token соответствует hash.
        """
        return self.hash_refresh_token(raw_token) == token_hash


class InMemoryAuthSessionRepository:
    """In-memory репозиторий refresh-сессий для unit-тестов."""

    def __init__(self) -> None:
        """Создает пустое хранилище refresh-сессий."""
        self.sessions_by_id: dict[UUID, AuthSession] = {}

    async def create(self, session: AuthSession) -> AuthSession:
        """Сохраняет refresh-сессию.

        Args:
            session: Refresh-сессия.

        Returns:
            Сохраненная refresh-сессия.
        """
        self.sessions_by_id[session.id] = session
        return session

    async def get_by_id(self, session_id: UUID) -> AuthSession | None:
        """Возвращает refresh-сессию по id.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            Refresh-сессия или None.
        """
        return self.sessions_by_id.get(session_id)

    async def get_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        """Возвращает refresh-сессию по hash refresh token.

        Args:
            refresh_token_hash: Hash refresh token.

        Returns:
            Refresh-сессия или None.
        """
        for session in self.sessions_by_id.values():
            if session.refresh_token_hash == refresh_token_hash:
                return session
        return None

    async def get_active_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        """Возвращает активную refresh-сессию по hash refresh token.

        Args:
            refresh_token_hash: Hash refresh token.

        Returns:
            Активная refresh-сессия или None.
        """
        session = await self.get_by_refresh_token_hash(refresh_token_hash)
        if session is None or not session.is_active():
            return None
        return session

    async def revoke(self, session_id: UUID) -> AuthSession | None:
        """Отзывает refresh-сессию.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            Отозванная refresh-сессия или None.
        """
        session = self.sessions_by_id.get(session_id)
        if session is None:
            return None
        session.revoke()
        return session

    async def exists_active(self, session_id: UUID) -> bool:
        """Проверяет наличие активной refresh-сессии.

        Args:
            session_id: Идентификатор refresh-сессии.

        Returns:
            True, если активная refresh-сессия есть.
        """
        session = self.sessions_by_id.get(session_id)
        return session is not None and session.is_active()


class FakeTransactionManager:
    """Тестовый менеджер транзакций."""

    async def __aenter__(self) -> None:
        """Открывает тестовую транзакцию."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Закрывает тестовую транзакцию.

        Args:
            exc_type: Тип исключения.
            exc: Экземпляр исключения.
            traceback: Traceback исключения.

        Returns:
            None, чтобы не подавлять исключения.
        """
        return None


def build_issue_use_case(
    sessions: InMemoryAuthSessionRepository,
    access_tokens: FakeAccessTokenService,
    refresh_tokens: FakeRefreshTokenService,
) -> IssueTokenPairUseCase:
    """Собирает use case выдачи token pair.

    Args:
        sessions: In-memory репозиторий refresh-сессий.
        access_tokens: Тестовый сервис access tokens.
        refresh_tokens: Тестовый сервис refresh tokens.

    Returns:
        Use case выдачи token pair.
    """
    return IssueTokenPairUseCase(
        access_tokens=access_tokens,
        refresh_tokens=refresh_tokens,
        sessions=sessions,
        transaction_manager=FakeTransactionManager(),
        refresh_token_ttl=timedelta(days=30),
    )


def build_refresh_use_case(
    sessions: InMemoryAuthSessionRepository,
    access_tokens: FakeAccessTokenService,
    refresh_tokens: FakeRefreshTokenService,
) -> RefreshTokenPairUseCase:
    """Собирает use case обновления token pair.

    Args:
        sessions: In-memory репозиторий refresh-сессий.
        access_tokens: Тестовый сервис access tokens.
        refresh_tokens: Тестовый сервис refresh tokens.

    Returns:
        Use case обновления token pair.
    """
    return RefreshTokenPairUseCase(
        access_tokens=access_tokens,
        refresh_tokens=refresh_tokens,
        sessions=sessions,
        transaction_manager=FakeTransactionManager(),
        refresh_token_ttl=timedelta(days=30),
    )


async def test_issue_token_pair_returns_access_token_and_refresh_token() -> None:
    """Проверяет, что issue возвращает access token и refresh token."""
    sessions = InMemoryAuthSessionRepository()
    access_tokens = FakeAccessTokenService()
    refresh_tokens = FakeRefreshTokenService()
    use_case = build_issue_use_case(sessions, access_tokens, refresh_tokens)

    token_pair = await use_case.execute(user_id=uuid4())

    assert token_pair.access_token == "access-1"
    assert token_pair.refresh_token == "refresh-1"
    assert token_pair.token_type == "bearer"


async def test_refresh_token_is_not_stored_as_raw_value() -> None:
    """Проверяет, что raw refresh token не сохраняется в сессии."""
    sessions = InMemoryAuthSessionRepository()
    access_tokens = FakeAccessTokenService()
    refresh_tokens = FakeRefreshTokenService()
    use_case = build_issue_use_case(sessions, access_tokens, refresh_tokens)

    token_pair = await use_case.execute(user_id=uuid4())
    stored_session = next(iter(sessions.sessions_by_id.values()))

    assert stored_session.refresh_token_hash == "hashed:refresh-1"
    assert stored_session.refresh_token_hash != token_pair.refresh_token


async def test_refresh_token_rotation_revokes_old_session() -> None:
    """Проверяет, что rotation отзывает старую refresh-сессию."""
    sessions = InMemoryAuthSessionRepository()
    access_tokens = FakeAccessTokenService()
    refresh_tokens = FakeRefreshTokenService()
    issue_use_case = build_issue_use_case(sessions, access_tokens, refresh_tokens)
    refresh_use_case = build_refresh_use_case(sessions, access_tokens, refresh_tokens)
    old_pair = await issue_use_case.execute(user_id=uuid4())
    old_session = next(iter(sessions.sessions_by_id.values()))

    new_pair = await refresh_use_case.execute(refresh_token=old_pair.refresh_token)

    assert not old_session.is_active()
    assert new_pair.access_token == "access-2"
    assert new_pair.refresh_token == "refresh-2"
    assert len(sessions.sessions_by_id) == 2


async def test_reusing_old_refresh_token_is_rejected() -> None:
    """Проверяет отказ при повторном использовании старого refresh token."""
    sessions = InMemoryAuthSessionRepository()
    access_tokens = FakeAccessTokenService()
    refresh_tokens = FakeRefreshTokenService()
    issue_use_case = build_issue_use_case(sessions, access_tokens, refresh_tokens)
    refresh_use_case = build_refresh_use_case(sessions, access_tokens, refresh_tokens)
    old_pair = await issue_use_case.execute(user_id=uuid4())
    await refresh_use_case.execute(refresh_token=old_pair.refresh_token)

    with pytest.raises(InvalidRefreshTokenError):
        await refresh_use_case.execute(refresh_token=old_pair.refresh_token)


async def test_expired_refresh_session_is_rejected() -> None:
    """Проверяет отказ для истекшей refresh-сессии."""
    sessions = InMemoryAuthSessionRepository()
    access_tokens = FakeAccessTokenService()
    refresh_tokens = FakeRefreshTokenService()
    user_id = uuid4()
    await sessions.create(
        AuthSession(
            user_id=user_id,
            refresh_token_hash="hashed:expired-refresh",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    refresh_use_case = build_refresh_use_case(sessions, access_tokens, refresh_tokens)

    with pytest.raises(ExpiredRefreshTokenError):
        await refresh_use_case.execute(refresh_token="expired-refresh")


async def test_revoked_refresh_session_is_rejected() -> None:
    """Проверяет отказ для отозванной refresh-сессии."""
    sessions = InMemoryAuthSessionRepository()
    access_tokens = FakeAccessTokenService()
    refresh_tokens = FakeRefreshTokenService()
    user_id = uuid4()
    session = await sessions.create(
        AuthSession(
            user_id=user_id,
            refresh_token_hash="hashed:revoked-refresh",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    revoke_use_case = RevokeRefreshSessionUseCase(
        refresh_tokens=refresh_tokens,
        sessions=sessions,
        transaction_manager=FakeTransactionManager(),
    )
    await revoke_use_case.execute(session_id=session.id)
    refresh_use_case = build_refresh_use_case(sessions, access_tokens, refresh_tokens)

    with pytest.raises(InvalidRefreshTokenError):
        await refresh_use_case.execute(refresh_token="revoked-refresh")
