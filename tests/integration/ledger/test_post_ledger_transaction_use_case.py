"""Интеграционные тесты use case posting ledger transaction."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.ledger.application.exceptions import (
    LedgerTransactionAlreadyExistsError,
)
from payflow.modules.ledger.application.use_cases import (
    PostLedgerEntryCommand,
    PostLedgerTransactionCommand,
    PostLedgerTransactionUseCase,
)
from payflow.modules.ledger.domain import (
    LedgerEntryDirection,
    LedgerOperationType,
    UnbalancedLedgerTransactionError,
)
from payflow.modules.ledger.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
)
from payflow.modules.ledger.infrastructure.repositories import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.ledger.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository
from payflow.modules.wallets.domain import Wallet
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletRepository,
)


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для integration теста ledger use case.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    repository = SQLAlchemyUserRepository(async_session)
    return await repository.create(User(email=f"{uuid4()}@example.com"))


async def create_wallet(async_session: AsyncSession, currency: str = "USD") -> Wallet:
    """Создает кошелек для integration теста ledger use case.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        currency: Код валюты кошелька.

    Returns:
        Созданный кошелек.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyWalletRepository(async_session)
    return await repository.create(Wallet(user_id=user.id, currency=currency))


def make_post_command(
    *,
    debit_wallet_id: UUID,
    credit_wallet_id: UUID,
    operation_id: UUID | None = None,
    debit_amount_minor: int = 100,
    credit_amount_minor: int = 100,
) -> PostLedgerTransactionCommand:
    """Создает команду posting ledger transaction для integration тестов.

    Args:
        debit_wallet_id: Идентификатор кошелька для DEBIT entry.
        credit_wallet_id: Идентификатор кошелька для CREDIT entry.
        operation_id: Идентификатор бизнес-операции.
        debit_amount_minor: Сумма DEBIT entry.
        credit_amount_minor: Сумма CREDIT entry.

    Returns:
        Команда posting ledger transaction.
    """
    return PostLedgerTransactionCommand(
        operation_id=operation_id if operation_id is not None else uuid4(),
        operation_type=LedgerOperationType.INTERNAL_DEPOSIT,
        entries=(
            PostLedgerEntryCommand(
                wallet_id=debit_wallet_id,
                direction=LedgerEntryDirection.DEBIT,
                amount_minor=debit_amount_minor,
                currency="USD",
            ),
            PostLedgerEntryCommand(
                wallet_id=credit_wallet_id,
                direction=LedgerEntryDirection.CREDIT,
                amount_minor=credit_amount_minor,
                currency="USD",
            ),
        ),
    )


def make_use_case(async_session: AsyncSession) -> PostLedgerTransactionUseCase:
    """Создает ledger posting use case с SQLAlchemy dependencies.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case posting ledger transaction.
    """
    return PostLedgerTransactionUseCase(
        transactions=SQLAlchemyLedgerTransactionRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


async def count_ledger_transactions(async_session: AsyncSession) -> int:
    """Считает ledger transactions в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество ledger transactions.
    """
    return await async_session.scalar(
        select(func.count()).select_from(LedgerTransactionModel)
    ) or 0


async def count_ledger_entries(async_session: AsyncSession) -> int:
    """Считает ledger entries в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество ledger entries.
    """
    return await async_session.scalar(
        select(func.count()).select_from(LedgerEntryModel)
    ) or 0


async def test_successful_posting_persists_transaction_and_entries(
    async_session: AsyncSession,
) -> None:
    """Проверяет сохранение ledger transaction и entries в БД.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    await async_session.commit()
    command = make_post_command(
        debit_wallet_id=debit_wallet.id,
        credit_wallet_id=credit_wallet.id,
    )

    transaction = await make_use_case(async_session).execute(command)

    stored_transaction = await async_session.get(
        LedgerTransactionModel,
        transaction.id,
    )
    entry_result = await async_session.scalars(
        select(LedgerEntryModel).where(
            LedgerEntryModel.transaction_id == transaction.id,
        )
    )
    stored_entries = entry_result.all()
    assert stored_transaction is not None
    assert stored_transaction.operation_id == command.operation_id
    assert stored_transaction.operation_type == LedgerOperationType.INTERNAL_DEPOSIT
    assert len(stored_entries) == 2
    assert {entry.wallet_id for entry in stored_entries} == {
        debit_wallet.id,
        credit_wallet.id,
    }


async def test_duplicate_operation_id_is_rejected(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ для duplicate operation_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    await async_session.commit()
    operation_id = uuid4()
    use_case = make_use_case(async_session)
    await use_case.execute(
        make_post_command(
            debit_wallet_id=debit_wallet.id,
            credit_wallet_id=credit_wallet.id,
            operation_id=operation_id,
        )
    )

    with pytest.raises(LedgerTransactionAlreadyExistsError):
        await use_case.execute(
            make_post_command(
                debit_wallet_id=debit_wallet.id,
                credit_wallet_id=credit_wallet.id,
                operation_id=operation_id,
            )
        )

    assert await count_ledger_transactions(async_session) == 1
    assert await count_ledger_entries(async_session) == 2


async def test_unbalanced_transaction_is_not_persisted(
    async_session: AsyncSession,
) -> None:
    """Проверяет, что unbalanced transaction не сохраняется.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    await async_session.commit()

    with pytest.raises(UnbalancedLedgerTransactionError):
        await make_use_case(async_session).execute(
            make_post_command(
                debit_wallet_id=debit_wallet.id,
                credit_wallet_id=credit_wallet.id,
                credit_amount_minor=90,
            )
        )

    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
