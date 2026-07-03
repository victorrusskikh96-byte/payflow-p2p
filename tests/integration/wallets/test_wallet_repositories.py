"""Интеграционные тесты SQLAlchemy-репозиториев кошельков."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository
from payflow.modules.wallets.domain import BalanceProjection, Wallet, WalletStatus
from payflow.modules.wallets.infrastructure.models import (
    WalletBalanceModel,
    WalletModel,
)
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для интеграционного теста кошельков.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    users = SQLAlchemyUserRepository(async_session)
    return await users.create(User(email=f"{uuid4()}@example.com"))


async def create_wallet(async_session: AsyncSession, currency: str = "USD") -> Wallet:
    """Создает кошелек для интеграционного теста.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        currency: Код валюты кошелька.

    Returns:
        Созданный кошелек.
    """
    user = await create_user(async_session)
    wallets = SQLAlchemyWalletRepository(async_session)
    return await wallets.create(Wallet(user_id=user.id, currency=currency))


async def test_create_wallet(async_session: AsyncSession) -> None:
    """Проверяет создание кошелька в PostgreSQL.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyWalletRepository(async_session)
    wallet = Wallet(user_id=user.id, currency="usd")

    created_wallet = await repository.create(wallet)

    stored_wallet = await async_session.get(WalletModel, created_wallet.id)
    assert stored_wallet is not None
    assert stored_wallet.user_id == user.id
    assert stored_wallet.currency == "USD"
    assert stored_wallet.status == WalletStatus.ACTIVE.value


async def test_get_wallet_by_id(async_session: AsyncSession) -> None:
    """Проверяет поиск кошелька по id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    created_wallet = await create_wallet(async_session)
    repository = SQLAlchemyWalletRepository(async_session)

    found_wallet = await repository.get_by_id(created_wallet.id)

    assert found_wallet == created_wallet


async def test_get_wallets_by_user_id(async_session: AsyncSession) -> None:
    """Проверяет поиск кошельков по user_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyWalletRepository(async_session)
    usd_wallet = await repository.create(Wallet(user_id=user.id, currency="USD"))
    eur_wallet = await repository.create(Wallet(user_id=user.id, currency="EUR"))
    other_user = await create_user(async_session)
    await repository.create(Wallet(user_id=other_user.id, currency="USD"))

    found_wallets = await repository.get_by_user_id(user.id)

    assert len(found_wallets) == 2
    assert {wallet.id for wallet in found_wallets} == {usd_wallet.id, eur_wallet.id}


async def test_get_wallet_by_user_id_and_currency(
    async_session: AsyncSession,
) -> None:
    """Проверяет поиск кошелька по user_id и currency.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyWalletRepository(async_session)
    created_wallet = await repository.create(Wallet(user_id=user.id, currency="USD"))

    found_wallet = await repository.get_by_user_id_and_currency(user.id, " usd ")

    assert found_wallet == created_wallet
    assert await repository.exists_by_user_id_and_currency(user.id, "usd")
    assert not await repository.exists_by_user_id_and_currency(user.id, "EUR")


async def test_wallet_user_id_and_currency_unique_constraint(
    async_session: AsyncSession,
) -> None:
    """Проверяет unique constraint на пару user_id и currency.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyWalletRepository(async_session)
    await repository.create(Wallet(user_id=user.id, currency="USD"))

    with pytest.raises(IntegrityError):
        await repository.create(Wallet(user_id=user.id, currency=" usd "))


async def test_create_initial_balance_projection(
    async_session: AsyncSession,
) -> None:
    """Проверяет создание начальной проекции баланса.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    balance = BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)

    created_balance = await repository.create_initial(balance)

    stored_balance = await async_session.get(WalletBalanceModel, wallet.id)
    assert stored_balance is not None
    assert created_balance.wallet_id == wallet.id
    assert stored_balance.available_amount_minor == 0
    assert stored_balance.locked_amount_minor == 0
    assert stored_balance.currency == "USD"


async def test_get_balance_projection_by_wallet_id(
    async_session: AsyncSession,
) -> None:
    """Проверяет поиск проекции баланса по wallet_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    created_balance = await repository.create_initial(
        BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
    )

    found_balance = await repository.get_by_wallet_id(wallet.id)

    assert found_balance == created_balance


async def test_wallet_requires_existing_user(async_session: AsyncSession) -> None:
    """Проверяет внешний ключ кошелька на users.id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyWalletRepository(async_session)

    with pytest.raises(IntegrityError):
        await repository.create(Wallet(user_id=uuid4(), currency="USD"))


async def test_balance_constraints_reject_negative_values(
    async_session: AsyncSession,
) -> None:
    """Проверяет запрет отрицательных значений в проекции баланса.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    balance_model = WalletBalanceModel(
        wallet_id=wallet.id,
        available_amount_minor=-1,
        locked_amount_minor=0,
        currency=wallet.currency,
        updated_at=wallet.updated_at,
    )
    async_session.add(balance_model)

    with pytest.raises(IntegrityError):
        await async_session.flush()
