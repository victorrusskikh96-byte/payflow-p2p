"""Unit-тесты use cases регистрации и аутентификации."""

from types import TracebackType
from uuid import UUID

import pytest

from payflow.modules.auth.application import (
    AuthenticateUserUseCase,
    GetCurrentUserUseCase,
    RegisterUserUseCase,
)
from payflow.modules.auth.domain import (
    AuthCredentials,
    CurrentUserBlockedError,
    CurrentUserNotFoundError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    WeakPasswordError,
)
from payflow.modules.users.domain import User, UserStatus


class FakeUserRepository:
    """Тестовый in-memory репозиторий пользователей."""

    def __init__(self) -> None:
        """Создает пустое in-memory хранилище пользователей."""
        self.users_by_email: dict[str, User] = {}

    async def create(self, user: User) -> User:
        """Сохраняет пользователя в in-memory хранилище.

        Args:
            user: Пользователь для сохранения.

        Returns:
            Сохраненный пользователь.
        """
        self.users_by_email[user.email] = user
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Ищет пользователя по идентификатору.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Пользователь или None, если он не найден.
        """
        for user in self.users_by_email.values():
            if user.id == user_id:
                return user
        return None

    async def get_by_email(self, email: str) -> User | None:
        """Ищет пользователя по нормализованному email.

        Args:
            email: Email пользователя.

        Returns:
            Пользователь или None, если он не найден.
        """
        return self.users_by_email.get(email.strip().lower())

    async def exists_by_email(self, email: str) -> bool:
        """Проверяет наличие пользователя по email.

        Args:
            email: Email пользователя.

        Returns:
            True, если пользователь есть в хранилище.
        """
        return email.strip().lower() in self.users_by_email


class FakeAuthCredentialsRepository:
    """Тестовый in-memory репозиторий учетных данных."""

    def __init__(self) -> None:
        """Создает пустое in-memory хранилище учетных данных."""
        self.credentials_by_user_id: dict[UUID, AuthCredentials] = {}

    async def create(self, credentials: AuthCredentials) -> AuthCredentials:
        """Сохраняет учетные данные пользователя.

        Args:
            credentials: Учетные данные для сохранения.

        Returns:
            Сохраненные учетные данные.
        """
        self.credentials_by_user_id[credentials.user_id] = credentials
        return credentials

    async def get_by_user_id(self, user_id: UUID) -> AuthCredentials | None:
        """Возвращает учетные данные по идентификатору пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Учетные данные или None, если они не найдены.
        """
        return self.credentials_by_user_id.get(user_id)


class FakePasswordHasher:
    """Тестовый хешер паролей с детерминированным результатом."""

    def hash_password(self, password: str) -> str:
        """Создает тестовый хеш пароля.

        Args:
            password: Пароль в открытом виде.

        Returns:
            Детерминированный тестовый хеш.
        """
        return f"hashed:{password}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Проверяет пароль по тестовому хешу.

        Args:
            password: Пароль в открытом виде.
            password_hash: Тестовый хеш пароля.

        Returns:
            True, если пароль соответствует хешу.
        """
        return password_hash == self.hash_password(password)


class FakeTransactionManager:
    """Тестовый менеджер транзакций, фиксирующий вход и выход."""

    def __init__(self) -> None:
        """Создает менеджер с начальными флагами состояния."""
        self.entered = False
        self.exited = False
        self.seen_exception: type[BaseException] | None = None

    async def __aenter__(self) -> None:
        """Фиксирует вход в транзакционный контекст."""
        self.entered = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Фиксирует выход из транзакционного контекста.

        Args:
            exc_type: Тип исключения внутри контекста.
            exc: Экземпляр исключения внутри контекста.
            traceback: Traceback исключения внутри контекста.

        Returns:
            None, чтобы не подавлять исключения.
        """
        self.exited = True
        self.seen_exception = exc_type
        return None


def build_register_use_case(
    users: FakeUserRepository,
    credentials: FakeAuthCredentialsRepository,
    transaction_manager: FakeTransactionManager,
) -> RegisterUserUseCase:
    """Собирает use case регистрации с тестовыми зависимостями.

    Args:
        users: Тестовый репозиторий пользователей.
        credentials: Тестовый репозиторий учетных данных.
        transaction_manager: Тестовый менеджер транзакций.

    Returns:
        Use case регистрации пользователя.
    """
    return RegisterUserUseCase(
        users=users,
        credentials=credentials,
        password_hasher=FakePasswordHasher(),
        transaction_manager=transaction_manager,
    )


def build_authenticate_use_case(
    users: FakeUserRepository,
    credentials: FakeAuthCredentialsRepository,
) -> AuthenticateUserUseCase:
    """Собирает use case аутентификации с тестовыми зависимостями.

    Args:
        users: Тестовый репозиторий пользователей.
        credentials: Тестовый репозиторий учетных данных.

    Returns:
        Use case аутентификации пользователя.
    """
    return AuthenticateUserUseCase(
        users=users,
        credentials=credentials,
        password_hasher=FakePasswordHasher(),
        transaction_manager=FakeTransactionManager(),
    )


def build_get_current_user_use_case(
    users: FakeUserRepository,
) -> GetCurrentUserUseCase:
    """Собирает use case получения текущего пользователя.

    Args:
        users: Тестовый репозиторий пользователей.

    Returns:
        Use case получения текущего пользователя.
    """
    return GetCurrentUserUseCase(users=users)


async def test_register_creates_user_and_auth_credentials() -> None:
    """Проверяет создание пользователя и учетных данных при регистрации."""
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    transaction_manager = FakeTransactionManager()
    use_case = build_register_use_case(users, credentials, transaction_manager)

    user = await use_case.execute(
        email="  User@Example.COM  ",
        password="valid-password",
    )

    stored_credentials = credentials.credentials_by_user_id[user.id]
    assert user.email == "user@example.com"
    assert stored_credentials.password_hash == "hashed:valid-password"
    assert transaction_manager.entered is True
    assert transaction_manager.exited is True


async def test_register_rejects_weak_password_before_transaction() -> None:
    """Проверяет отказ по слабому паролю до открытия транзакции."""
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    transaction_manager = FakeTransactionManager()
    use_case = build_register_use_case(users, credentials, transaction_manager)

    with pytest.raises(WeakPasswordError):
        await use_case.execute(email="user@example.com", password="short")

    assert transaction_manager.entered is False
    assert users.users_by_email == {}
    assert credentials.credentials_by_user_id == {}


async def test_register_rejects_duplicate_email() -> None:
    """Проверяет отказ регистрации при повторном email."""
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    transaction_manager = FakeTransactionManager()
    await users.create(User(email="user@example.com"))
    use_case = build_register_use_case(users, credentials, transaction_manager)

    with pytest.raises(EmailAlreadyRegisteredError):
        await use_case.execute(email="USER@example.com", password="valid-password")

    assert credentials.credentials_by_user_id == {}
    assert transaction_manager.seen_exception is EmailAlreadyRegisteredError


async def test_authenticate_returns_user_for_valid_credentials() -> None:
    """Проверяет успешную аутентификацию по корректным данным."""
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    user = await users.create(User(email="user@example.com"))
    await credentials.create(
        AuthCredentials(user_id=user.id, password_hash="hashed:valid-password")
    )
    use_case = build_authenticate_use_case(users, credentials)

    authenticated_user = await use_case.execute(
        email="USER@example.com",
        password="valid-password",
    )

    assert authenticated_user == user


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("missing@example.com", "valid-password"),
        ("user@example.com", "wrong-password"),
    ],
)
async def test_authenticate_rejects_invalid_credentials(
    email: str,
    password: str,
) -> None:
    """Проверяет отказ при неверных учетных данных.

    Args:
        email: Email из параметров теста.
        password: Пароль из параметров теста.
    """
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    user = await users.create(User(email="user@example.com"))
    await credentials.create(
        AuthCredentials(user_id=user.id, password_hash="hashed:valid-password")
    )
    use_case = build_authenticate_use_case(users, credentials)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email=email, password=password)


async def test_authenticate_rejects_user_without_credentials() -> None:
    """Проверяет отказ для пользователя без учетных данных."""
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    await users.create(User(email="user@example.com"))
    use_case = build_authenticate_use_case(users, credentials)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="user@example.com", password="valid-password")


async def test_authenticate_rejects_blocked_user() -> None:
    """Проверяет отказ в аутентификации заблокированного пользователя."""
    users = FakeUserRepository()
    credentials = FakeAuthCredentialsRepository()
    user = await users.create(User(email="user@example.com", status=UserStatus.BLOCKED))
    await credentials.create(
        AuthCredentials(user_id=user.id, password_hash="hashed:valid-password")
    )
    use_case = build_authenticate_use_case(users, credentials)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="user@example.com", password="valid-password")


async def test_get_current_user_returns_active_user() -> None:
    """Проверяет получение активного текущего пользователя."""
    users = FakeUserRepository()
    user = await users.create(User(email="user@example.com"))
    use_case = build_get_current_user_use_case(users)

    current_user = await use_case.execute(user_id=user.id)

    assert current_user == user


async def test_get_current_user_rejects_missing_user() -> None:
    """Проверяет отказ, если пользователь из access token не найден."""
    users = FakeUserRepository()
    use_case = build_get_current_user_use_case(users)

    with pytest.raises(CurrentUserNotFoundError):
        await use_case.execute(user_id=UUID("00000000-0000-0000-0000-000000000001"))


async def test_get_current_user_rejects_blocked_user() -> None:
    """Проверяет отказ для заблокированного текущего пользователя."""
    users = FakeUserRepository()
    user = await users.create(User(email="user@example.com", status=UserStatus.BLOCKED))
    use_case = build_get_current_user_use_case(users)

    with pytest.raises(CurrentUserBlockedError):
        await use_case.execute(user_id=user.id)
