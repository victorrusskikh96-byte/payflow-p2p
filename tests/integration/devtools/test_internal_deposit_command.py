"""Интеграционные тесты dev-only команды internal deposit."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payflow.devtools.internal_deposit import (
    DEV_FUNDING_INITIAL_BALANCE_MINOR,
    DEV_FUNDING_USER_EMAIL,
    DevInternalDepositEnvironmentError,
    DevInternalDepositInputError,
    run_internal_deposit,
)
from payflow.modules.financial_core.domain.ledger import (
    LedgerEntryDirection,
    LedgerOperationType,
)
from payflow.modules.financial_core.domain.wallets import BalanceProjection, Wallet
from payflow.modules.financial_core.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
    OutboxEventModel,
    WalletBalanceModel,
)
from payflow.modules.financial_core.infrastructure.repositories.wallets import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


async def create_wallet_with_balance(
    session: AsyncSession,
    *,
    currency: str = "RUB",
    available_amount_minor: int = 0,
) -> Wallet:
    """Создает пользовательский wallet с начальной balance projection.

    Args:
        session: Асинхронная SQLAlchemy-сессия.
        currency: Валюта кошелька.
        available_amount_minor: Начальная доступная сумма.

    Returns:
        Созданный wallet.
    """
    users = SQLAlchemyUserRepository(session)
    wallets = SQLAlchemyWalletRepository(session)
    balances = SQLAlchemyWalletBalanceRepository(session)
    user = await users.create(User(email=f"{uuid4()}@example.com"))
    wallet = await wallets.create(Wallet(user_id=user.id, currency=currency))
    await balances.create_initial(
        BalanceProjection(
            wallet_id=wallet.id,
            currency=wallet.currency,
            available_amount_minor=available_amount_minor,
        )
    )
    return wallet


async def get_available_balance(session: AsyncSession, wallet_id: UUID) -> int:
    """Возвращает доступный баланс кошелька.

    Args:
        session: Асинхронная SQLAlchemy-сессия.
        wallet_id: Идентификатор кошелька.

    Returns:
        Доступная сумма в минорных единицах.
    """
    balance = await session.get(WalletBalanceModel, wallet_id)
    assert balance is not None
    return balance.available_amount_minor


async def count_ledger_transactions(session: AsyncSession) -> int:
    """Считает ledger transactions.

    Args:
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество ledger transactions.
    """
    return int(
        await session.scalar(select(func.count()).select_from(LedgerTransactionModel))
        or 0
    )


async def count_ledger_entries(session: AsyncSession) -> int:
    """Считает ledger entries.

    Args:
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество ledger entries.
    """
    return int(
        await session.scalar(select(func.count()).select_from(LedgerEntryModel)) or 0
    )


async def count_internal_deposit_outbox_events(session: AsyncSession) -> int:
    """Считает outbox events успешного internal deposit.

    Args:
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество событий `internal_deposit.completed`.
    """
    return int(
        await session.scalar(
            select(func.count())
            .select_from(OutboxEventModel)
            .where(OutboxEventModel.event_type == "internal_deposit.completed")
        )
        or 0
    )


async def get_dev_funding_wallet_id(session: AsyncSession) -> UUID:
    """Возвращает wallet id dev funding wallet.

    Args:
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Идентификатор dev funding wallet.
    """
    user = await SQLAlchemyUserRepository(session).get_by_email(DEV_FUNDING_USER_EMAIL)
    assert user is not None
    wallet = await SQLAlchemyWalletRepository(session).get_by_user_id_and_currency(
        user.id,
        "RUB",
    )
    assert wallet is not None
    return wallet.id


async def test_dev_command_uses_application_flow_and_persists_financial_records(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет баланс, ledger entries и outbox после dev deposit.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    async with async_session_factory() as session:
        wallet = await create_wallet_with_balance(session, available_amount_minor=25)
        await session.commit()

    operation_id = uuid4()
    result = await run_internal_deposit(
        wallet_id=wallet.id,
        amount_minor=100_000,
        currency="rub",
        operation_id=operation_id,
        session_factory=async_session_factory,
        app_env="test",
    )

    async with async_session_factory() as session:
        source_wallet_id = await get_dev_funding_wallet_id(session)
        stored_transaction = await session.get(
            LedgerTransactionModel,
            result.ledger_transaction_id,
        )
        entries = (
            await session.scalars(
                select(LedgerEntryModel).where(
                    LedgerEntryModel.transaction_id == result.ledger_transaction_id,
                )
            )
        ).all()
        event = await session.scalar(
            select(OutboxEventModel).where(
                OutboxEventModel.event_type == "internal_deposit.completed",
            )
        )

        assert result.operation_id == operation_id
        assert result.wallet_id == wallet.id
        assert result.amount_minor == 100_000
        assert result.currency == "RUB"
        assert stored_transaction is not None
        assert stored_transaction.operation_id == operation_id
        assert stored_transaction.operation_type == LedgerOperationType.INTERNAL_DEPOSIT
        assert len(entries) == 2
        assert {
            (entry.wallet_id, entry.direction, entry.amount_minor, entry.currency)
            for entry in entries
        } == {
            (source_wallet_id, LedgerEntryDirection.DEBIT.value, 100_000, "RUB"),
            (wallet.id, LedgerEntryDirection.CREDIT.value, 100_000, "RUB"),
        }
        assert await get_available_balance(session, wallet.id) == 100_025
        assert (
            await get_available_balance(session, source_wallet_id)
            == DEV_FUNDING_INITIAL_BALANCE_MINOR - 100_000
        )
        assert event is not None
        assert event.aggregate_type == "internal_deposit"
        assert event.aggregate_id == str(operation_id)
        assert event.payload["target_wallet_id"] == str(wallet.id)
        assert event.payload["amount_minor"] == 100_000
        assert event.payload["currency"] == "RUB"
        assert await count_ledger_transactions(session) == 1
        assert await count_ledger_entries(session) == 2
        assert await count_internal_deposit_outbox_events(session) == 1


async def test_dev_command_is_disabled_in_production_like_environment(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет отказ команды в production-like окружении.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    async with async_session_factory() as session:
        wallet = await create_wallet_with_balance(session)
        await session.commit()

    with pytest.raises(DevInternalDepositEnvironmentError):
        await run_internal_deposit(
            wallet_id=wallet.id,
            amount_minor=100,
            currency="RUB",
            session_factory=async_session_factory,
            app_env="production",
        )

    async with async_session_factory() as session:
        assert await get_available_balance(session, wallet.id) == 0
        assert await count_ledger_transactions(session) == 0
        assert await count_ledger_entries(session) == 0
        assert await count_internal_deposit_outbox_events(session) == 0


@pytest.mark.parametrize("amount_minor", [0, -1])
async def test_dev_command_rejects_non_positive_amount(
    async_session_factory: async_sessionmaker[AsyncSession],
    amount_minor: int,
) -> None:
    """Проверяет отказ для неположительной суммы.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
        amount_minor: Некорректная сумма команды.
    """
    async with async_session_factory() as session:
        wallet = await create_wallet_with_balance(session)
        await session.commit()

    with pytest.raises(DevInternalDepositInputError):
        await run_internal_deposit(
            wallet_id=wallet.id,
            amount_minor=amount_minor,
            currency="RUB",
            session_factory=async_session_factory,
            app_env="test",
        )

    async with async_session_factory() as session:
        assert await get_available_balance(session, wallet.id) == 0
        assert await count_ledger_transactions(session) == 0
        assert await count_ledger_entries(session) == 0
        assert await count_internal_deposit_outbox_events(session) == 0


async def test_dev_command_rejects_invalid_wallet_id(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет отказ для wallet_id в неверном формате.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    with pytest.raises(DevInternalDepositInputError):
        await run_internal_deposit(
            wallet_id="not-a-uuid",
            amount_minor=100,
            currency="RUB",
            session_factory=async_session_factory,
            app_env="test",
        )

    async with async_session_factory() as session:
        assert await count_ledger_transactions(session) == 0
        assert await count_ledger_entries(session) == 0
        assert await count_internal_deposit_outbox_events(session) == 0
