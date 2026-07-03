"""E2E-тесты HTTP endpoints кошельков."""

from typing import Any, cast

from httpx import AsyncClient


async def register_user_and_get_access_token(
    api_client: AsyncClient,
    *,
    email: str,
) -> str:
    """Регистрирует пользователя и возвращает JWT access token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        email: Email регистрируемого пользователя.

    Returns:
        JWT access token.
    """
    response = await api_client.post(
        "/auth/register",
        json={"email": email, "password": "valid-password"},
    )
    body = cast(dict[str, Any], response.json())

    assert response.status_code == 201
    return cast(str, body["access_token"])


def auth_headers(access_token: str) -> dict[str, str]:
    """Возвращает Authorization header для JWT access token.

    Args:
        access_token: JWT access token.

    Returns:
        Словарь HTTP headers.
    """
    return {"Authorization": f"Bearer {access_token}"}


def assert_zero_balance(body: dict[str, Any]) -> None:
    """Проверяет нулевую проекцию баланса в ответе кошелька.

    Args:
        body: JSON-тело ответа API.
    """
    balance = cast(dict[str, Any], body["balance"])
    assert balance["available_amount_minor"] == 0
    assert balance["locked_amount_minor"] == 0


async def create_wallet(
    api_client: AsyncClient,
    *,
    access_token: str,
    currency: str,
) -> dict[str, Any]:
    """Создает кошелек через HTTP API и возвращает JSON-ответ.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        access_token: JWT access token владельца кошелька.
        currency: Код валюты кошелька.

    Returns:
        JSON-тело ответа с кошельком и балансом.
    """
    response = await api_client.post(
        "/wallets",
        json={"currency": currency},
        headers=auth_headers(access_token),
    )
    body = cast(dict[str, Any], response.json())

    assert response.status_code == 201
    return body


async def test_authenticated_user_can_create_wallet(
    api_client: AsyncClient,
) -> None:
    """Проверяет создание кошелька аутентифицированным пользователем.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    access_token = await register_user_and_get_access_token(
        api_client,
        email="wallet-user@example.com",
    )

    body = await create_wallet(
        api_client,
        access_token=access_token,
        currency="usd",
    )
    wallet = cast(dict[str, Any], body["wallet"])

    assert wallet["currency"] == "USD"
    assert wallet["status"] == "ACTIVE"
    assert_zero_balance(body)


async def test_unauthenticated_create_wallet_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет 401 для создания кошелька без access token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.post("/wallets", json={"currency": "USD"})

    assert response.status_code == 401


async def test_duplicate_wallet_currency_returns_conflict(
    api_client: AsyncClient,
) -> None:
    """Проверяет конфликт при повторной валюте кошелька пользователя.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    access_token = await register_user_and_get_access_token(
        api_client,
        email="duplicate-wallet-user@example.com",
    )
    await create_wallet(api_client, access_token=access_token, currency="USD")

    response = await api_client.post(
        "/wallets",
        json={"currency": " usd "},
        headers=auth_headers(access_token),
    )

    assert response.status_code == 409


async def test_user_can_get_list_of_own_wallets(
    api_client: AsyncClient,
) -> None:
    """Проверяет получение списка собственных кошельков.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    access_token = await register_user_and_get_access_token(
        api_client,
        email="wallet-list-user@example.com",
    )
    await create_wallet(api_client, access_token=access_token, currency="USD")
    await create_wallet(api_client, access_token=access_token, currency="EUR")

    response = await api_client.get("/wallets/me", headers=auth_headers(access_token))
    body = cast(list[dict[str, Any]], response.json())

    assert response.status_code == 200
    assert {item["wallet"]["currency"] for item in body} == {"USD", "EUR"}
    assert all(item["wallet"]["user_id"] for item in body)


async def test_user_can_get_own_wallet_by_id(api_client: AsyncClient) -> None:
    """Проверяет получение собственного кошелька по id.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    access_token = await register_user_and_get_access_token(
        api_client,
        email="wallet-by-id-user@example.com",
    )
    created_wallet = await create_wallet(
        api_client,
        access_token=access_token,
        currency="USD",
    )
    wallet_id = cast(dict[str, Any], created_wallet["wallet"])["id"]

    response = await api_client.get(
        f"/wallets/{wallet_id}",
        headers=auth_headers(access_token),
    )
    body = cast(dict[str, Any], response.json())

    assert response.status_code == 200
    assert body["wallet"]["id"] == wallet_id
    assert_zero_balance(body)


async def test_user_cannot_get_another_users_wallet(
    api_client: AsyncClient,
) -> None:
    """Проверяет безопасный 404 для чужого кошелька.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    first_access_token = await register_user_and_get_access_token(
        api_client,
        email="wallet-owner@example.com",
    )
    second_access_token = await register_user_and_get_access_token(
        api_client,
        email="wallet-intruder@example.com",
    )
    created_wallet = await create_wallet(
        api_client,
        access_token=first_access_token,
        currency="USD",
    )
    wallet_id = cast(dict[str, Any], created_wallet["wallet"])["id"]

    response = await api_client.get(
        f"/wallets/{wallet_id}",
        headers=auth_headers(second_access_token),
    )

    assert response.status_code == 404


async def test_wallet_response_contains_zero_balance_projection(
    api_client: AsyncClient,
) -> None:
    """Проверяет наличие нулевой balance projection в ответе кошелька.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    access_token = await register_user_and_get_access_token(
        api_client,
        email="wallet-balance-user@example.com",
    )

    body = await create_wallet(
        api_client,
        access_token=access_token,
        currency="USD",
    )

    assert body["balance"]["currency"] == "USD"
    assert body["balance"]["wallet_id"] == body["wallet"]["id"]
    assert_zero_balance(body)
