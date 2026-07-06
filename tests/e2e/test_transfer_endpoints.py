"""E2E-тесты HTTP endpoints P2P-переводов."""

from typing import Any, cast
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payflow.modules.wallets.infrastructure.models import WalletBalanceModel
from tests.e2e.test_wallet_endpoints import (
    auth_headers,
    count_outbox_events,
    create_wallet,
    register_user_and_get_access_token,
)


async def set_wallet_available_balance(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    wallet_id: str,
    available_amount_minor: int,
) -> None:
    """Устанавливает доступный баланс кошелька для предусловий E2E-теста.

    Args:
        session_factory: Фабрика асинхронных SQLAlchemy-сессий.
        wallet_id: Идентификатор кошелька.
        available_amount_minor: Доступная сумма в минорных единицах.
    """
    async with session_factory() as session:
        balance = await session.get(WalletBalanceModel, UUID(wallet_id))
        assert balance is not None
        balance.available_amount_minor = available_amount_minor
        await session.commit()


async def make_user_wallet(
    api_client: AsyncClient,
    *,
    email: str,
    currency: str = "USD",
) -> tuple[str, dict[str, Any]]:
    """Создает пользователя с кошельком через HTTP API.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        email: Email регистрируемого пользователя.
        currency: Код валюты кошелька.

    Returns:
        JWT access token и JSON-тело ответа создания кошелька.
    """
    access_token = await register_user_and_get_access_token(
        api_client,
        email=email,
    )
    wallet_body = await create_wallet(
        api_client,
        access_token=access_token,
        currency=currency,
    )
    return access_token, wallet_body


def wallet_id(wallet_body: dict[str, Any]) -> str:
    """Возвращает идентификатор кошелька из JSON-ответа API.

    Args:
        wallet_body: JSON-тело ответа создания или получения кошелька.

    Returns:
        Идентификатор кошелька.
    """
    wallet = cast(dict[str, Any], wallet_body["wallet"])
    return cast(str, wallet["id"])


async def create_transfer(
    api_client: AsyncClient,
    *,
    access_token: str,
    sender_wallet_id: str,
    recipient_wallet_id: str,
    amount_minor: int,
    operation_id: str | None = None,
    currency: str = "USD",
) -> dict[str, Any]:
    """Создает P2P-перевод через HTTP API и возвращает JSON-ответ.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        access_token: JWT access token отправителя.
        sender_wallet_id: Идентификатор кошелька отправителя.
        recipient_wallet_id: Идентификатор кошелька получателя.
        amount_minor: Сумма перевода в минорных единицах.
        operation_id: Идемпотентный идентификатор операции.
        currency: Код валюты перевода.

    Returns:
        JSON-тело ответа с P2P-переводом.
    """
    response = await api_client.post(
        "/transfers",
        json={
            "operation_id": operation_id or str(uuid4()),
            "sender_wallet_id": sender_wallet_id,
            "recipient_wallet_id": recipient_wallet_id,
            "amount_minor": amount_minor,
            "currency": currency,
        },
        headers=auth_headers(access_token),
    )
    body = cast(dict[str, Any], response.json())

    assert response.status_code == 201
    return body


async def test_authenticated_user_can_create_transfer(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет создание P2P-перевода аутентифицированным пользователем.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    sender_token, sender_wallet = await make_user_wallet(
        api_client,
        email="transfer-sender@example.com",
    )
    _, recipient_wallet = await make_user_wallet(
        api_client,
        email="transfer-recipient@example.com",
    )
    sender_wallet_id = wallet_id(sender_wallet)
    recipient_wallet_id = wallet_id(recipient_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=sender_wallet_id,
        available_amount_minor=1_000,
    )

    body = await create_transfer(
        api_client,
        access_token=sender_token,
        sender_wallet_id=sender_wallet_id,
        recipient_wallet_id=recipient_wallet_id,
        amount_minor=250,
    )

    assert body["sender_wallet_id"] == sender_wallet_id
    assert body["recipient_wallet_id"] == recipient_wallet_id
    assert body["amount_minor"] == 250
    assert body["currency"] == "USD"
    assert body["status"] == "COMPLETED"
    assert body["ledger_transaction_id"] is not None
    assert (
        await count_outbox_events(
            e2e_async_session_factory,
            event_type="p2p_transfer.completed",
        )
        == 1
    )


async def test_unauthenticated_create_transfer_returns_unauthorized(
    api_client: AsyncClient,
) -> None:
    """Проверяет 401 для создания P2P-перевода без access token.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
    """
    response = await api_client.post(
        "/transfers",
        json={
            "operation_id": str(uuid4()),
            "sender_wallet_id": str(uuid4()),
            "recipient_wallet_id": str(uuid4()),
            "amount_minor": 100,
            "currency": "USD",
        },
    )

    assert response.status_code == 401


async def test_user_cannot_transfer_from_another_users_wallet(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет запрет перевода с чужого кошелька.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    first_token, first_wallet = await make_user_wallet(
        api_client,
        email="transfer-owner-a@example.com",
    )
    _, second_wallet = await make_user_wallet(
        api_client,
        email="transfer-owner-b@example.com",
    )
    first_wallet_id = wallet_id(first_wallet)
    second_wallet_id = wallet_id(second_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=second_wallet_id,
        available_amount_minor=1_000,
    )

    response = await api_client.post(
        "/transfers",
        json={
            "operation_id": str(uuid4()),
            "sender_wallet_id": second_wallet_id,
            "recipient_wallet_id": first_wallet_id,
            "amount_minor": 100,
            "currency": "USD",
        },
        headers=auth_headers(first_token),
    )

    assert response.status_code == 404
    assert (
        await count_outbox_events(
            e2e_async_session_factory,
            event_type="p2p_transfer.completed",
        )
        == 0
    )


async def test_insufficient_funds_returns_error(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет ошибку при недостаточном балансе отправителя.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    sender_token, sender_wallet = await make_user_wallet(
        api_client,
        email="transfer-low-balance@example.com",
    )
    _, recipient_wallet = await make_user_wallet(
        api_client,
        email="transfer-low-balance-recipient@example.com",
    )
    sender_wallet_id = wallet_id(sender_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=sender_wallet_id,
        available_amount_minor=100,
    )

    response = await api_client.post(
        "/transfers",
        json={
            "operation_id": str(uuid4()),
            "sender_wallet_id": sender_wallet_id,
            "recipient_wallet_id": wallet_id(recipient_wallet),
            "amount_minor": 250,
            "currency": "USD",
        },
        headers=auth_headers(sender_token),
    )

    assert response.status_code == 409
    assert (
        await count_outbox_events(
            e2e_async_session_factory,
            event_type="p2p_transfer.completed",
        )
        == 0
    )


async def test_same_wallet_transfer_returns_error(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет ошибку при переводе на тот же кошелек.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    access_token, wallet = await make_user_wallet(
        api_client,
        email="transfer-same-wallet@example.com",
    )
    same_wallet_id = wallet_id(wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=same_wallet_id,
        available_amount_minor=1_000,
    )

    response = await api_client.post(
        "/transfers",
        json={
            "operation_id": str(uuid4()),
            "sender_wallet_id": same_wallet_id,
            "recipient_wallet_id": same_wallet_id,
            "amount_minor": 100,
            "currency": "USD",
        },
        headers=auth_headers(access_token),
    )

    assert response.status_code == 400


async def test_duplicate_operation_id_returns_conflict(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет конфликт при повторном operation_id.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    sender_token, sender_wallet = await make_user_wallet(
        api_client,
        email="transfer-duplicate@example.com",
    )
    _, recipient_wallet = await make_user_wallet(
        api_client,
        email="transfer-duplicate-recipient@example.com",
    )
    sender_wallet_id = wallet_id(sender_wallet)
    recipient_wallet_id = wallet_id(recipient_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=sender_wallet_id,
        available_amount_minor=1_000,
    )
    operation_id = str(uuid4())
    await create_transfer(
        api_client,
        access_token=sender_token,
        sender_wallet_id=sender_wallet_id,
        recipient_wallet_id=recipient_wallet_id,
        amount_minor=100,
        operation_id=operation_id,
    )

    response = await api_client.post(
        "/transfers",
        json={
            "operation_id": operation_id,
            "sender_wallet_id": sender_wallet_id,
            "recipient_wallet_id": recipient_wallet_id,
            "amount_minor": 100,
            "currency": "USD",
        },
        headers=auth_headers(sender_token),
    )

    assert response.status_code == 409
    assert (
        await count_outbox_events(
            e2e_async_session_factory,
            event_type="p2p_transfer.completed",
        )
        == 1
    )


async def test_user_can_list_own_transfers(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет, что пользователь видит только свои исходящие переводы.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    first_token, first_wallet = await make_user_wallet(
        api_client,
        email="transfer-list-first@example.com",
    )
    second_token, second_wallet = await make_user_wallet(
        api_client,
        email="transfer-list-second@example.com",
    )
    first_wallet_id = wallet_id(first_wallet)
    second_wallet_id = wallet_id(second_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=first_wallet_id,
        available_amount_minor=1_000,
    )
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=second_wallet_id,
        available_amount_minor=1_000,
    )
    own_transfer = await create_transfer(
        api_client,
        access_token=first_token,
        sender_wallet_id=first_wallet_id,
        recipient_wallet_id=second_wallet_id,
        amount_minor=100,
    )
    await create_transfer(
        api_client,
        access_token=second_token,
        sender_wallet_id=second_wallet_id,
        recipient_wallet_id=first_wallet_id,
        amount_minor=50,
    )

    response = await api_client.get(
        "/transfers/me",
        headers=auth_headers(first_token),
    )
    body = cast(dict[str, Any], response.json())
    transfers = cast(list[dict[str, Any]], body["transfers"])

    assert response.status_code == 200
    assert [transfer["id"] for transfer in transfers] == [own_transfer["id"]]


async def test_user_cannot_get_another_users_transfer(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет безопасный 404 для чужого P2P-перевода.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    first_token, first_wallet = await make_user_wallet(
        api_client,
        email="transfer-private-first@example.com",
    )
    second_token, second_wallet = await make_user_wallet(
        api_client,
        email="transfer-private-second@example.com",
    )
    first_wallet_id = wallet_id(first_wallet)
    second_wallet_id = wallet_id(second_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=first_wallet_id,
        available_amount_minor=1_000,
    )
    transfer = await create_transfer(
        api_client,
        access_token=first_token,
        sender_wallet_id=first_wallet_id,
        recipient_wallet_id=second_wallet_id,
        amount_minor=100,
    )

    response = await api_client.get(
        f"/transfers/{transfer['id']}",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


async def test_balances_changed_correctly_after_successful_transfer(
    api_client: AsyncClient,
    e2e_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет изменение балансов после успешного P2P-перевода.

    Args:
        api_client: HTTP-клиент FastAPI с тестовой базой данных.
        e2e_async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    sender_token, sender_wallet = await make_user_wallet(
        api_client,
        email="transfer-balance-sender@example.com",
    )
    recipient_token, recipient_wallet = await make_user_wallet(
        api_client,
        email="transfer-balance-recipient@example.com",
    )
    sender_wallet_id = wallet_id(sender_wallet)
    recipient_wallet_id = wallet_id(recipient_wallet)
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=sender_wallet_id,
        available_amount_minor=1_000,
    )
    await set_wallet_available_balance(
        e2e_async_session_factory,
        wallet_id=recipient_wallet_id,
        available_amount_minor=25,
    )

    await create_transfer(
        api_client,
        access_token=sender_token,
        sender_wallet_id=sender_wallet_id,
        recipient_wallet_id=recipient_wallet_id,
        amount_minor=250,
    )

    sender_response = await api_client.get(
        f"/wallets/{sender_wallet_id}",
        headers=auth_headers(sender_token),
    )
    recipient_response = await api_client.get(
        f"/wallets/{recipient_wallet_id}",
        headers=auth_headers(recipient_token),
    )
    sender_body = cast(dict[str, Any], sender_response.json())
    recipient_body = cast(dict[str, Any], recipient_response.json())

    assert sender_response.status_code == 200
    assert recipient_response.status_code == 200
    assert sender_body["balance"]["available_amount_minor"] == 750
    assert recipient_body["balance"]["available_amount_minor"] == 275
