"""Use cases регистрации и аутентификации пользователей."""

from payflow.modules.auth.application.password_hasher import PasswordHasher
from payflow.modules.auth.application.repositories import AuthCredentialsRepository
from payflow.modules.auth.application.transactions import TransactionManager
from payflow.modules.auth.domain import (
    AuthCredentials,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
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
    ) -> None:
        """Создает use case аутентификации пользователя.

        Args:
            users: Репозиторий пользователей.
            credentials: Репозиторий учетных данных.
            password_hasher: Сервис проверки паролей.
        """
        self._users = users
        self._credentials = credentials
        self._password_hasher = password_hasher

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
