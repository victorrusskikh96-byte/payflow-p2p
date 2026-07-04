"""Интеграционные тесты SQLAlchemy-репозитория ledger."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.ledger.domain import (
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
    LedgerTransactionStatus,
)
from payflow.modules.ledger.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
)
from payflow.modules.ledger.infrastructure.repositories import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository
from payflow.modules.wallets.domain import Wallet
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletRepository,
)


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для интеграционного теста ledger.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    repository = SQLAlchemyUserRepository(async_session)
    return await repository.create(User(email=f"{uuid4()}@example.com"))


async def create_wallet(async_session: AsyncSession, currency: str = "USD") -> Wallet:
    """Создает кошелек для интеграционного теста ledger.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        currency: Код валюты кошелька.

    Returns:
        Созданный кошелек.
    """
    user = await create_user(async_session)
    repository = SQLAlchemyWalletRepository(async_session)
    return await repository.create(Wallet(user_id=user.id, currency=currency))


def make_ledger_transaction(
    *,
    debit_wallet_id: UUID,
    credit_wallet_id: UUID,
    amount_minor: int = 100,
    operation_id: UUID | None = None,
    transaction_id: UUID | None = None,
) -> LedgerTransaction:
    """Создает ledger transaction для интеграционного теста.

    Args:
        debit_wallet_id: Идентификатор кошелька для DEBIT entry.
        credit_wallet_id: Идентификатор кошелька для CREDIT entry.
        amount_minor: Сумма в минорных единицах.
        operation_id: Идентификатор бизнес-операции.
        transaction_id: Идентификатор ledger transaction.

    Returns:
        Ledger transaction с двумя сбалансированными entries.
    """
    resolved_transaction_id = transaction_id if transaction_id is not None else uuid4()
    return LedgerTransaction(
        id=resolved_transaction_id,
        operation_id=operation_id if operation_id is not None else uuid4(),
        operation_type=LedgerOperationType.P2P_TRANSFER,
        status=LedgerTransactionStatus.COMMITTED,
        entries=(
            LedgerEntry(
                transaction_id=resolved_transaction_id,
                wallet_id=debit_wallet_id,
                direction=LedgerEntryDirection.DEBIT,
                amount_minor=amount_minor,
                currency="USD",
            ),
            LedgerEntry(
                transaction_id=resolved_transaction_id,
                wallet_id=credit_wallet_id,
                direction=LedgerEntryDirection.CREDIT,
                amount_minor=amount_minor,
                currency="USD",
            ),
        ),
    )


async def test_create_ledger_transaction_with_entries(
    async_session: AsyncSession,
) -> None:
    """Проверяет создание ledger transaction вместе с entries.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    repository = SQLAlchemyLedgerTransactionRepository(async_session)
    transaction = make_ledger_transaction(
        debit_wallet_id=debit_wallet.id,
        credit_wallet_id=credit_wallet.id,
    )

    created_transaction = await repository.create(transaction)

    stored_transaction = await async_session.get(
        LedgerTransactionModel,
        created_transaction.id,
    )
    entry_result = await async_session.scalars(
        select(LedgerEntryModel).where(
            LedgerEntryModel.transaction_id == created_transaction.id,
        ),
    )
    stored_entries = entry_result.all()
    assert stored_transaction is not None
    assert stored_transaction.operation_id == transaction.operation_id
    assert stored_transaction.status == LedgerTransactionStatus.COMMITTED.value
    assert len(stored_entries) == 2
    assert {entry.wallet_id for entry in stored_entries} == {
        debit_wallet.id,
        credit_wallet.id,
    }


async def test_get_ledger_transaction_by_id(async_session: AsyncSession) -> None:
    """Проверяет поиск ledger transaction по id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    repository = SQLAlchemyLedgerTransactionRepository(async_session)
    created_transaction = await repository.create(
        make_ledger_transaction(
            debit_wallet_id=debit_wallet.id,
            credit_wallet_id=credit_wallet.id,
        ),
    )

    found_transaction = await repository.get_by_id(created_transaction.id)

    assert found_transaction == created_transaction


async def test_get_ledger_transaction_by_operation_id(
    async_session: AsyncSession,
) -> None:
    """Проверяет поиск ledger transaction по operation_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    operation_id = uuid4()
    repository = SQLAlchemyLedgerTransactionRepository(async_session)
    created_transaction = await repository.create(
        make_ledger_transaction(
            debit_wallet_id=debit_wallet.id,
            credit_wallet_id=credit_wallet.id,
            operation_id=operation_id,
        ),
    )

    found_transaction = await repository.get_by_operation_id(operation_id)

    assert found_transaction == created_transaction
    assert await repository.exists_by_operation_id(operation_id)
    assert not await repository.exists_by_operation_id(uuid4())


async def test_get_ledger_entries_by_wallet_id(async_session: AsyncSession) -> None:
    """Проверяет поиск ledger entries по wallet_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    target_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    other_wallet = await create_wallet(async_session)
    repository = SQLAlchemyLedgerTransactionRepository(async_session)
    target_transaction = await repository.create(
        make_ledger_transaction(
            debit_wallet_id=target_wallet.id,
            credit_wallet_id=credit_wallet.id,
        ),
    )
    await repository.create(
        make_ledger_transaction(
            debit_wallet_id=other_wallet.id,
            credit_wallet_id=credit_wallet.id,
        ),
    )

    entries = await repository.get_entries_by_wallet_id(target_wallet.id)

    assert len(entries) == 1
    assert entries[0].wallet_id == target_wallet.id
    assert entries[0] in target_transaction.entries


async def test_operation_id_unique_constraint(async_session: AsyncSession) -> None:
    """Проверяет unique constraint на operation_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    credit_wallet = await create_wallet(async_session)
    operation_id = uuid4()
    repository = SQLAlchemyLedgerTransactionRepository(async_session)
    await repository.create(
        make_ledger_transaction(
            debit_wallet_id=debit_wallet.id,
            credit_wallet_id=credit_wallet.id,
            operation_id=operation_id,
        ),
    )

    with pytest.raises(IntegrityError):
        await repository.create(
            make_ledger_transaction(
                debit_wallet_id=debit_wallet.id,
                credit_wallet_id=credit_wallet.id,
                operation_id=operation_id,
            ),
        )


async def test_entry_wallet_id_foreign_key_constraint(
    async_session: AsyncSession,
) -> None:
    """Проверяет внешний ключ ledger entry на wallets.id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    repository = SQLAlchemyLedgerTransactionRepository(async_session)

    with pytest.raises(IntegrityError):
        await repository.create(
            make_ledger_transaction(
                debit_wallet_id=debit_wallet.id,
                credit_wallet_id=uuid4(),
            ),
        )


@pytest.mark.parametrize("amount_minor", [0, -1])
async def test_entry_amount_minor_database_constraint(
    async_session: AsyncSession,
    amount_minor: int,
) -> None:
    """Проверяет запрет неположительной суммы ledger entry на уровне БД.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        amount_minor: Неположительная сумма из параметров теста.
    """
    wallet = await create_wallet(async_session)
    transaction_id = uuid4()
    now = datetime.now(UTC)
    async_session.add(
        LedgerTransactionModel(
            id=transaction_id,
            operation_id=uuid4(),
            operation_type=LedgerOperationType.P2P_TRANSFER.value,
            status=LedgerTransactionStatus.COMMITTED.value,
            created_at=now,
            updated_at=now,
        ),
    )
    await async_session.flush()
    async_session.add(
        LedgerEntryModel(
            id=uuid4(),
            transaction_id=transaction_id,
            wallet_id=wallet.id,
            direction=LedgerEntryDirection.DEBIT.value,
            amount_minor=amount_minor,
            currency=wallet.currency,
            created_at=now,
        ),
    )

    with pytest.raises(IntegrityError):
        await async_session.flush()


async def test_create_ledger_transaction_is_atomic(
    async_session: AsyncSession,
) -> None:
    """Проверяет атомарность сохранения transaction и entries.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    debit_wallet = await create_wallet(async_session)
    operation_id = uuid4()
    transaction = make_ledger_transaction(
        debit_wallet_id=debit_wallet.id,
        credit_wallet_id=uuid4(),
        operation_id=operation_id,
    )
    repository = SQLAlchemyLedgerTransactionRepository(async_session)

    with pytest.raises(IntegrityError):
        await repository.create(transaction)

    await async_session.rollback()

    assert await repository.get_by_operation_id(operation_id) is None
    assert not await repository.exists_by_operation_id(operation_id)
