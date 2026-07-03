"""E2E-тесты HTTP endpoints аутентификации."""

from typing import Any, cast

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payflow.modules.users.domain import UserStatus
from payflow.modules.users.infrastructure.models import UserModel


def assert_token_pair_response(body: dict[str, Any]) -> None:
    """Проверяет наличие непустых access и refresh tokens в ответе.

    Args:
        body: JSON-тело ответа API.
    """
    assert isinstance(body["access_token"], str)
    assert body["access_token"]
    assert isinstance(body["refresh_token"], str)
    assert body["refresh_token"]


async def register_user_and_get_token_pair(
    api_client: AsyncClient,
    *,
    email: str = "user@example.com",
    password: str = "valid-password",
) -> dict[str, Any]:
    """Регистрирует пользователя и возвращает JSON token pair.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        email: Email регистрируемого пользователя.
        password: Пароль регистрируемого пользователя.

    Returns:
        JSON-тело ответа с token pair.
    """
    response = await api_client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    body = cast(dict[str, Any], response.json())

    assert response.status_code == 201
    assert_token_pair_response(body)
    return body


async def block_user_by_email(
    session_factory: async_sessionmaker[AsyncSession],
    email: str,
) -> None:
    """Блокирует пользователя по email в тестовой базе.

    Args:
        session_factory: Фабрика асинхронных SQLAlchemy-сессий.
        email: Email пользователя.

    Raises:
        AssertionError: Если пользователь не найден в тестовой базе.
    """
    async with session_factory() as session:
        user_model = await session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        assert user_model is not None
        user_model.status = UserStatus.BLOCKED.value
        await session.commit()


async def test_register_user_success(api_client: AsyncClient) -> None:
    """Проверяет успешную регистрацию пользователя через HTTP API.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "valid-password"},
    )

    body = cast(dict[str, Any], response.json())

    assert response.status_code == 201
    assert_token_pair_response(body)


async def test_repeated_register_user_returns_conflict(
    api_client: AsyncClient,
) -> None:
    """Проверяет ошибку при повторной регистрации того же email.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    payload = {"email": "user@example.com", "password": "valid-password"}
    first_response = await api_client.post("/auth/register", json=payload)

    second_response = await api_client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


async def test_login_user_success(api_client: AsyncClient) -> None:
    """Проверяет успешный login через HTTP API.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    payload = {"email": "user@example.com", "password": "valid-password"}
    register_response = await api_client.post("/auth/register", json=payload)

    response = await api_client.post("/auth/login", json=payload)
    body = cast(dict[str, Any], response.json())

    assert register_response.status_code == 201
    assert response.status_code == 200
    assert_token_pair_response(body)


async def test_login_with_wrong_password_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет ошибку login при неверном пароле.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    register_response = await api_client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "valid-password"},
    )

    response = await api_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert register_response.status_code == 201
    assert response.status_code == 401


async def test_refresh_returns_new_token_pair(api_client: AsyncClient) -> None:
    """Проверяет успешную ротацию refresh token через HTTP API.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    original_pair = await register_user_and_get_token_pair(api_client)

    response = await api_client.post(
        "/auth/refresh",
        json={"refresh_token": original_pair["refresh_token"]},
    )
    refreshed_pair = cast(dict[str, Any], response.json())

    assert response.status_code == 200
    assert_token_pair_response(refreshed_pair)
    assert refreshed_pair["refresh_token"] != original_pair["refresh_token"]


async def test_refresh_rejects_reused_refresh_token(
    api_client: AsyncClient,
) -> None:
    """Проверяет запрет повторного использования старого refresh token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    original_pair = await register_user_and_get_token_pair(api_client)
    refresh_response = await api_client.post(
        "/auth/refresh",
        json={"refresh_token": original_pair["refresh_token"]},
    )

    reused_response = await api_client.post(
        "/auth/refresh",
        json={"refresh_token": original_pair["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    assert reused_response.status_code == 401


async def test_refresh_with_invalid_token_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет ошибку refresh при невалидном refresh token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid-refresh-token"},
    )

    assert response.status_code == 401


async def test_logout_revokes_refresh_session(api_client: AsyncClient) -> None:
    """Проверяет успешный logout и отзыв refresh-сессии.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    token_pair = await register_user_and_get_token_pair(api_client)

    logout_response = await api_client.post(
        "/auth/logout",
        json={"refresh_token": token_pair["refresh_token"]},
    )
    refresh_response = await api_client.post(
        "/auth/refresh",
        json={"refresh_token": token_pair["refresh_token"]},
    )

    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "ok"}
    assert refresh_response.status_code == 401


async def test_logout_with_invalid_token_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет ошибку logout при невалидном refresh token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.post(
        "/auth/logout",
        json={"refresh_token": "invalid-refresh-token"},
    )

    assert response.status_code == 401


async def test_me_returns_current_user_with_valid_access_token(
    api_client: AsyncClient,
) -> None:
    """Проверяет получение текущего пользователя по валидному access token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    token_pair = await register_user_and_get_token_pair(
        api_client,
        email="me@example.com",
    )

    response = await api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_pair['access_token']}"},
    )
    body = cast(dict[str, Any], response.json())

    assert response.status_code == 200
    assert body["email"] == "me@example.com"
    assert body["status"] == UserStatus.ACTIVE.value
    assert isinstance(body["id"], str)
    assert isinstance(body["created_at"], str)
    assert isinstance(body["updated_at"], str)


async def test_me_without_token_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет 401 при запросе текущего пользователя без token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.get("/auth/me")

    assert response.status_code == 401


async def test_me_with_invalid_token_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет 401 при запросе текущего пользователя с невалидным token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-access-token"},
    )

    assert response.status_code == 401


async def test_me_with_blocked_user_token_returns_forbidden(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет 403 для access token заблокированного пользователя.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    token_pair = await register_user_and_get_token_pair(
        api_client,
        email="blocked@example.com",
    )
    await block_user_by_email(e2e_async_session_factory, "blocked@example.com")

    response = await api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_pair['access_token']}"},
    )

    assert response.status_code == 403
