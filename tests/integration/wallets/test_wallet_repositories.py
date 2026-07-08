"""Интеграционные тесты SQLAlchemy-репозиториев кошельков."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    InsufficientFundsError,
    InvalidBalanceUpdateError,
    Wallet,
    WalletAlreadyExistsError,
    WalletStatus,
)
from payflow.modules.financial_core.infrastructure.models import (
    WalletBalanceModel,
    WalletModel,
)
from payflow.modules.financial_core.infrastructure.repositories.wallets import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


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

    with pytest.raises(WalletAlreadyExistsError):
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


async def test_get_balance_projection_by_wallet_id_for_update(
    async_session: AsyncSession,
) -> None:
    """Проверяет получение проекции баланса с row-level lock.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    created_balance = await repository.create_initial(
        BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
    )

    locked_balance = await repository.get_by_wallet_id_for_update(wallet.id)

    assert locked_balance == created_balance


async def test_get_balance_projection_for_update_locks_row(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет, что SELECT FOR UPDATE блокирует строку баланса.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    async with async_session_factory() as setup_session:
        wallet = await create_wallet(setup_session, currency="USD")
        setup_repository = SQLAlchemyWalletBalanceRepository(setup_session)
        await setup_repository.create_initial(
            BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
        )
        await setup_session.commit()

    locker_session = async_session_factory()
    contender_session = async_session_factory()
    try:
        await locker_session.begin()
        locker_repository = SQLAlchemyWalletBalanceRepository(locker_session)
        await locker_repository.get_by_wallet_id_for_update(wallet.id)

        await contender_session.begin()
        await contender_session.execute(text("SET LOCAL lock_timeout = '100ms'"))
        contender_repository = SQLAlchemyWalletBalanceRepository(contender_session)

        with pytest.raises(DBAPIError):
            await contender_repository.get_by_wallet_id_for_update(wallet.id)
    finally:
        await contender_session.rollback()
        await locker_session.rollback()
        await contender_session.close()
        await locker_session.close()


async def test_increase_available_balance(async_session: AsyncSession) -> None:
    """Проверяет увеличение доступного баланса в PostgreSQL.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    await repository.create_initial(
        BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
    )
    balance = await repository.get_by_wallet_id_for_update(wallet.id)

    updated_balance = await repository.increase_available_amount(balance, 150)

    stored_balance = await async_session.get(WalletBalanceModel, wallet.id)
    assert stored_balance is not None
    assert updated_balance.available_amount_minor == 150
    assert stored_balance.available_amount_minor == 150


async def test_decrease_available_balance_with_sufficient_funds(
    async_session: AsyncSession,
) -> None:
    """Проверяет уменьшение доступного баланса при достаточной сумме.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    await repository.create_initial(
        BalanceProjection(
            wallet_id=wallet.id,
            currency=wallet.currency,
            available_amount_minor=150,
        )
    )
    balance = await repository.get_by_wallet_id_for_update(wallet.id)

    updated_balance = await repository.decrease_available_amount(balance, 40)

    stored_balance = await async_session.get(WalletBalanceModel, wallet.id)
    assert stored_balance is not None
    assert updated_balance.available_amount_minor == 110
    assert stored_balance.available_amount_minor == 110


async def test_decrease_available_balance_rejects_negative_result(
    async_session: AsyncSession,
) -> None:
    """Проверяет запрет уменьшения доступного баланса ниже нуля.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    await repository.create_initial(
        BalanceProjection(
            wallet_id=wallet.id,
            currency=wallet.currency,
            available_amount_minor=30,
        )
    )
    balance = await repository.get_by_wallet_id_for_update(wallet.id)

    with pytest.raises(InsufficientFundsError):
        await repository.decrease_available_amount(balance, 31)

    stored_balance = await async_session.get(WalletBalanceModel, wallet.id)
    assert stored_balance is not None
    assert stored_balance.available_amount_minor == 30


async def test_has_sufficient_available_balance(
    async_session: AsyncSession,
) -> None:
    """Проверяет репозиторную проверку достаточности доступного баланса.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    await repository.create_initial(
        BalanceProjection(
            wallet_id=wallet.id,
            currency=wallet.currency,
            available_amount_minor=50,
        )
    )

    assert await repository.has_sufficient_available_balance(wallet.id, 50)
    assert not await repository.has_sufficient_available_balance(wallet.id, 51)


async def test_save_rejects_negative_locked_balance(
    async_session: AsyncSession,
) -> None:
    """Проверяет запрет отрицательного locked balance при сохранении.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    await repository.create_initial(
        BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
    )
    balance = await repository.get_by_wallet_id_for_update(wallet.id)
    balance.locked_amount_minor = -1

    with pytest.raises(InvalidBalanceUpdateError):
        await repository.save(balance)

    stored_balance = await async_session.get(WalletBalanceModel, wallet.id)
    assert stored_balance is not None
    assert stored_balance.locked_amount_minor == 0


async def test_save_rejects_currency_mismatch_with_wallet(
    async_session: AsyncSession,
) -> None:
    """Проверяет запрет рассинхронизации валюты баланса и кошелька.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    wallet = await create_wallet(async_session, currency="USD")
    repository = SQLAlchemyWalletBalanceRepository(async_session)
    await repository.create_initial(
        BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
    )
    balance = await repository.get_by_wallet_id_for_update(wallet.id)
    balance.currency = "EUR"

    with pytest.raises(InvalidBalanceUpdateError):
        await repository.save(balance)


async def test_balance_update_is_persisted_after_commit(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет сохранение обновленной проекции после commit.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    async with async_session_factory() as setup_session:
        wallet = await create_wallet(setup_session, currency="USD")
        setup_repository = SQLAlchemyWalletBalanceRepository(setup_session)
        await setup_repository.create_initial(
            BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
        )
        await setup_session.commit()

    async with async_session_factory() as update_session:
        update_repository = SQLAlchemyWalletBalanceRepository(update_session)
        balance = await update_repository.get_by_wallet_id_for_update(wallet.id)
        await update_repository.increase_available_amount(balance, 250)
        await update_session.commit()

    async with async_session_factory() as read_session:
        read_repository = SQLAlchemyWalletBalanceRepository(read_session)
        stored_balance = await read_repository.get_by_wallet_id(wallet.id)

    assert stored_balance is not None
    assert stored_balance.available_amount_minor == 250


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
