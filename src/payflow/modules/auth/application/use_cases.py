"""Use cases регистрации, аутентификации и выдачи токенов."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from payflow.modules.auth.application.access_tokens import AccessTokenService
from payflow.modules.auth.application.password_hasher import PasswordHasher
from payflow.modules.auth.application.refresh_tokens import RefreshTokenService
from payflow.modules.auth.application.repositories import (
    AuthCredentialsRepository,
    AuthSessionRepository,
)
from payflow.modules.auth.application.token_pairs import TokenPair
from payflow.modules.auth.application.transactions import TransactionManager
from payflow.modules.auth.domain import (
    AuthCredentials,
    AuthSession,
    CurrentUserBlockedError,
    CurrentUserNotFoundError,
    EmailAlreadyRegisteredError,
    ExpiredRefreshTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    validate_password,
)
from payflow.modules.users.application.repositories import UserRepository
from payflow.modules.users.domain import User, UserStatus


class RegisterUserUseCase:
    """Регистрирует пользователя и создает его учетные данные."""

    def __init__(
        self,
        *,
        users: UserRepository,
        credentials: AuthCredentialsRepository,
        password_hasher: PasswordHasher,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case регистрации пользователя.

        Args:
            users: Репозиторий пользователей.
            credentials: Репозиторий учетных данных.
            password_hasher: Сервис хеширования паролей.
            transaction_manager: Менеджер транзакции регистрации.
        """
        self._users = users
        self._credentials = credentials
        self._password_hasher = password_hasher
        self._transaction_manager = transaction_manager

    async def execute(self, *, email: str, password: str) -> User:
        """Регистрирует пользователя с email и паролем.

        Args:
            email: Email нового пользователя.
            password: Пароль нового пользователя.

        Returns:
            Созданный пользователь.

        Raises:
            WeakPasswordError: Если пароль не соответствует политике.
            EmailAlreadyRegisteredError: Если email уже зарегистрирован.
        """
        validate_password(password)

        async with self._transaction_manager:
            if await self._users.exists_by_email(email):
                raise EmailAlreadyRegisteredError(
                    "User with this email already exists."
                )

            user = await self._users.create(User(email=email))
            password_hash = self._password_hasher.hash_password(password)
            await self._credentials.create(
                AuthCredentials(user_id=user.id, password_hash=password_hash)
            )

            return user


class AuthenticateUserUseCase:
    """Проверяет учетные данные пользователя для входа."""

    def __init__(
        self,
        *,
        users: UserRepository,
        credentials: AuthCredentialsRepository,
        password_hasher: PasswordHasher,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case аутентификации пользователя.

        Args:
            users: Репозиторий пользователей.
            credentials: Репозиторий учетных данных.
            password_hasher: Сервис проверки паролей.
            transaction_manager: Менеджер транзакции аутентификации.
        """
        self._users = users
        self._credentials = credentials
        self._password_hasher = password_hasher
        self._transaction_manager = transaction_manager

    async def execute(self, *, email: str, password: str) -> User:
        """Аутентифицирует пользователя по email и паролю.

        Args:
            email: Email пользователя.
            password: Пароль пользователя.

        Returns:
            Аутентифицированный пользователь.

        Raises:
            InvalidCredentialsError: Если пользователь, пароль или статус невалидны.
        """
        async with self._transaction_manager:
            user = await self._users.get_by_email(email)
            if user is None or user.status is UserStatus.BLOCKED:
                raise InvalidCredentialsError("Invalid email or password.")

            credentials = await self._credentials.get_by_user_id(user.id)
            if credentials is None:
                raise InvalidCredentialsError("Invalid email or password.")

            if not self._password_hasher.verify_password(
                password, credentials.password_hash
            ):
                raise InvalidCredentialsError("Invalid email or password.")

            return user


class GetCurrentUserUseCase:
    """Возвращает текущего пользователя по user_id из access token."""

    def __init__(self, *, users: UserRepository) -> None:
        """Создает use case получения текущего пользователя.

        Args:
            users: Репозиторий пользователей.
        """
        self._users = users

    async def execute(self, *, user_id: UUID) -> User:
        """Возвращает активного пользователя для защищенного запроса.

        Args:
            user_id: Идентификатор пользователя из проверенного access token.

        Returns:
            Доменная сущность текущего пользователя.

        Raises:
            CurrentUserNotFoundError: Если пользователь из token не найден.
            CurrentUserBlockedError: Если пользователь заблокирован.
        """
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise CurrentUserNotFoundError("Current user was not found.")

        if user.status is UserStatus.BLOCKED:
            raise CurrentUserBlockedError("Current user is blocked.")

        return user


class IssueTokenPairUseCase:
    """Выпускает новую пару access и refresh tokens для пользователя."""

    def __init__(
        self,
        *,
        access_tokens: AccessTokenService,
        refresh_tokens: RefreshTokenService,
        sessions: AuthSessionRepository,
        transaction_manager: TransactionManager,
        refresh_token_ttl: timedelta,
    ) -> None:
        """Создает use case выдачи token pair.

        Args:
            access_tokens: Сервис выпуска JWT access tokens.
            refresh_tokens: Сервис генерации opaque refresh tokens.
            sessions: Репозиторий refresh-сессий.
            transaction_manager: Менеджер транзакции.
            refresh_token_ttl: Время жизни refresh token.
        """
        self._access_tokens = access_tokens
        self._refresh_tokens = refresh_tokens
        self._sessions = sessions
        self._transaction_manager = transaction_manager
        self._refresh_token_ttl = refresh_token_ttl

    async def execute(self, *, user_id: UUID) -> TokenPair:
        """Выпускает token pair и сохраняет hash refresh token.

        Args:
            user_id: Идентификатор пользователя-владельца token pair.

        Returns:
            DTO с access token, refresh token и сроками действия.
        """
        async with self._transaction_manager:
            return await self._issue_token_pair(user_id=user_id)

    async def _issue_token_pair(self, *, user_id: UUID) -> TokenPair:
        access_token = self._access_tokens.create_access_token(user_id)
        access_payload = self._access_tokens.decode_access_token(access_token)
        refresh_token = self._refresh_tokens.generate_refresh_token()
        refresh_token_hash = self._refresh_tokens.hash_refresh_token(refresh_token)
        refresh_expires_at = datetime.now(UTC) + self._refresh_token_ttl

        await self._sessions.create(
            AuthSession(
                user_id=user_id,
                refresh_token_hash=refresh_token_hash,
                expires_at=refresh_expires_at,
            )
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            access_expires_at=access_payload.expires_at,
            refresh_expires_at=refresh_expires_at,
        )


class RefreshTokenPairUseCase:
    """Обновляет token pair через refresh token rotation."""

    def __init__(
        self,
        *,
        access_tokens: AccessTokenService,
        refresh_tokens: RefreshTokenService,
        sessions: AuthSessionRepository,
        transaction_manager: TransactionManager,
        refresh_token_ttl: timedelta,
    ) -> None:
        """Создает use case обновления token pair.

        Args:
            access_tokens: Сервис выпуска JWT access tokens.
            refresh_tokens: Сервис генерации и хеширования refresh tokens.
            sessions: Репозиторий refresh-сессий.
            transaction_manager: Менеджер транзакции.
            refresh_token_ttl: Время жизни нового refresh token.
        """
        self._issuer = IssueTokenPairUseCase(
            access_tokens=access_tokens,
            refresh_tokens=refresh_tokens,
            sessions=sessions,
            transaction_manager=transaction_manager,
            refresh_token_ttl=refresh_token_ttl,
        )
        self._refresh_tokens = refresh_tokens
        self._sessions = sessions
        self._transaction_manager = transaction_manager

    async def execute(self, *, refresh_token: str) -> TokenPair:
        """Ротирует refresh token и возвращает новый token pair.

        Args:
            refresh_token: Raw opaque refresh token.

        Returns:
            Новая пара access и refresh tokens.

        Raises:
            InvalidRefreshTokenError: Если refresh token не найден или отозван.
            ExpiredRefreshTokenError: Если refresh-сессия истекла.
        """
        refresh_token_hash = self._refresh_tokens.hash_refresh_token(refresh_token)

        async with self._transaction_manager:
            session = await self._get_valid_session(
                refresh_token=refresh_token,
                refresh_token_hash=refresh_token_hash,
            )
            await self._sessions.revoke(session.id)
            return await self._issuer._issue_token_pair(user_id=session.user_id)

    async def _get_valid_session(
        self,
        *,
        refresh_token: str,
        refresh_token_hash: str,
    ) -> AuthSession:
        session = await self._sessions.get_by_refresh_token_hash(refresh_token_hash)
        if session is None:
            raise InvalidRefreshTokenError("Invalid refresh token.")

        if not self._refresh_tokens.verify_refresh_token(
            refresh_token,
            session.refresh_token_hash,
        ):
            raise InvalidRefreshTokenError("Invalid refresh token.")

        if session.expires_at <= datetime.now(UTC):
            raise ExpiredRefreshTokenError("Refresh token has expired.")

        if not session.is_active():
            raise InvalidRefreshTokenError("Refresh token session is not active.")

        return session


class RevokeRefreshSessionUseCase:
    """Отзывает активную refresh-сессию по token или session id."""

    def __init__(
        self,
        *,
        refresh_tokens: RefreshTokenService,
        sessions: AuthSessionRepository,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case отзыва refresh-сессии.

        Args:
            refresh_tokens: Сервис хеширования refresh tokens.
            sessions: Репозиторий refresh-сессий.
            transaction_manager: Менеджер транзакции.
        """
        self._refresh_tokens = refresh_tokens
        self._sessions = sessions
        self._transaction_manager = transaction_manager

    async def execute(
        self,
        *,
        refresh_token: str | None = None,
        session_id: UUID | None = None,
    ) -> AuthSession:
        """Отзывает активную refresh-сессию.

        Args:
            refresh_token: Raw opaque refresh token.
            session_id: Идентификатор refresh-сессии.

        Returns:
            Отозванная refresh-сессия.

        Raises:
            ValueError: Если переданы оба идентификатора или не передан ни один.
            InvalidRefreshTokenError: Если refresh-сессия не найдена или неактивна.
            ExpiredRefreshTokenError: Если refresh-сессия истекла.
        """
        if (refresh_token is None) == (session_id is None):
            raise ValueError("Pass either refresh_token or session_id.")

        async with self._transaction_manager:
            session = await self._get_active_session(
                refresh_token=refresh_token,
                session_id=session_id,
            )
            revoked_session = await self._sessions.revoke(session.id)
            if revoked_session is None:
                raise InvalidRefreshTokenError("Refresh session was not found.")
            return revoked_session

    async def _get_active_session(
        self,
        *,
        refresh_token: str | None,
        session_id: UUID | None,
    ) -> AuthSession:
        if refresh_token is not None:
            refresh_token_hash = self._refresh_tokens.hash_refresh_token(refresh_token)
            session = await self._sessions.get_by_refresh_token_hash(refresh_token_hash)
        elif session_id is not None:
            session = await self._sessions.get_by_id(session_id)
        else:
            raise ValueError("Pass either refresh_token or session_id.")

        if session is None:
            raise InvalidRefreshTokenError("Refresh session was not found.")

        if session.expires_at <= datetime.now(UTC):
            raise ExpiredRefreshTokenError("Refresh token has expired.")

        if not session.is_active():
            raise InvalidRefreshTokenError("Refresh token session is not active.")

        return session
