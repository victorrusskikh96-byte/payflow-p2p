"""Интеграционные тесты use case создания кошелька."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.outbox.domain import OutboxEvent
from payflow.modules.outbox.infrastructure.models import OutboxEventModel
from payflow.modules.outbox.infrastructure.repositories import (
    SQLAlchemyOutboxEventRepository,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository
from payflow.modules.wallets.application.use_cases import CreateWalletUseCase
from payflow.modules.wallets.domain import WalletAlreadyExistsError
from payflow.modules.wallets.infrastructure.models import (
    WalletBalanceModel,
    WalletModel,
)
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.wallets.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)


class FailingOutboxEventRepository(SQLAlchemyOutboxEventRepository):
    """Имитирует сбой сохранения outbox event внутри БД-транзакции."""

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Выбрасывает RuntimeError вместо сохранения события.

        Args:
            event: Доменное outbox event.

        Returns:
            Сохраненное outbox event.

        Raises:
            RuntimeError: Всегда, чтобы проверить rollback операции.
        """
        raise RuntimeError("Forced wallet outbox failure.")


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для integration-теста wallets.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    users = SQLAlchemyUserRepository(async_session)
    return await users.create(User(email=f"{uuid4()}@example.com"))


def make_use_case(
    async_session: AsyncSession,
    *,
    fail_outbox: bool = False,
) -> CreateWalletUseCase:
    """Создает use case открытия кошелька с SQLAlchemy dependencies.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        fail_outbox: Нужно ли заменить outbox repository на падающий.

    Returns:
        Use case создания кошелька.
    """
    outbox_events = (
        FailingOutboxEventRepository(async_session)
        if fail_outbox
        else SQLAlchemyOutboxEventRepository(async_session)
    )
    return CreateWalletUseCase(
        users=SQLAlchemyUserRepository(async_session),
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=SQLAlchemyWalletBalanceRepository(async_session),
        outbox_events=outbox_events,
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


async def count_wallets(async_session: AsyncSession) -> int:
    """Считает кошельки в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество кошельков.
    """
    return int(
        await async_session.scalar(select(func.count()).select_from(WalletModel)) or 0
    )


async def count_balances(async_session: AsyncSession) -> int:
    """Считает balance projections в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество balance projections.
    """
    return int(
        await async_session.scalar(select(func.count()).select_from(WalletBalanceModel))
        or 0
    )


async def count_outbox_events(
    async_session: AsyncSession,
    *,
    event_type: str,
) -> int:
    """Считает outbox events заданного типа.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        event_type: Тип события outbox.

    Returns:
        Количество outbox events.
    """
    return int(
        await async_session.scalar(
            select(func.count())
            .select_from(OutboxEventModel)
            .where(OutboxEventModel.event_type == event_type)
        )
        or 0
    )


async def get_balance(
    async_session: AsyncSession,
    wallet_id: UUID,
) -> WalletBalanceModel:
    """Возвращает balance projection из базы данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        wallet_id: Идентификатор кошелька.

    Returns:
        ORM-модель balance projection.
    """
    balance = await async_session.get(WalletBalanceModel, wallet_id)
    assert balance is not None
    return balance


async def test_successful_wallet_creation_persists_wallet_balance_and_outbox(
    async_session: AsyncSession,
) -> None:
    """Проверяет атомарное создание wallet, balance и outbox event.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    await async_session.commit()

    result = await make_use_case(async_session).execute(
        user_id=user.id,
        currency=" usd ",
    )

    stored_wallet = await async_session.get(WalletModel, result.wallet.id)
    stored_balance = await get_balance(async_session, result.wallet.id)

    assert stored_wallet is not None
    assert stored_wallet.user_id == user.id
    assert stored_wallet.currency == "USD"
    assert stored_balance.available_amount_minor == 0
    assert stored_balance.locked_amount_minor == 0
    assert stored_balance.currency == "USD"
    assert await count_outbox_events(async_session, event_type="wallet.created") == 1


async def test_duplicate_wallet_creation_does_not_create_extra_outbox_event(
    async_session: AsyncSession,
) -> None:
    """Проверяет, что duplicate wallet не создает лишний outbox event.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    await async_session.commit()
    use_case = make_use_case(async_session)
    await use_case.execute(user_id=user.id, currency="USD")

    with pytest.raises(WalletAlreadyExistsError):
        await use_case.execute(user_id=user.id, currency=" usd ")

    assert await count_wallets(async_session) == 1
    assert await count_balances(async_session) == 1
    assert await count_outbox_events(async_session, event_type="wallet.created") == 1


async def test_failed_outbox_creation_rolls_back_wallet_and_balance(
    async_session: AsyncSession,
) -> None:
    """Проверяет rollback wallet и balance при сбое outbox event.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    await async_session.commit()

    with pytest.raises(RuntimeError, match="Forced wallet outbox failure"):
        await make_use_case(async_session, fail_outbox=True).execute(
            user_id=user.id,
            currency="USD",
        )

    async_session.expire_all()
    assert await count_wallets(async_session) == 0
    assert await count_balances(async_session) == 0
    assert await count_outbox_events(async_session, event_type="wallet.created") == 0


async def test_wallet_creation_reuses_external_transaction_without_committing(
    async_session: AsyncSession,
) -> None:
    """Проверяет, что use case не коммитит активную внешнюю транзакцию.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    user = await create_user(async_session)
    await async_session.commit()
    await async_session.begin()

    await make_use_case(async_session).execute(user_id=user.id, currency="USD")

    assert async_session.in_transaction()
    await async_session.rollback()
    async_session.expire_all()
    assert await count_wallets(async_session) == 0
    assert await count_balances(async_session) == 0
    assert await count_outbox_events(async_session, event_type="wallet.created") == 0
