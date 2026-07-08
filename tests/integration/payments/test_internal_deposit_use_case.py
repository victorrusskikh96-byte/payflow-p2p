"""Интеграционные тесты use case внутреннего пополнения кошелька."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.financial_core.application.events import (
    OutboxEventData,
    OutboxEventRecord,
)
from payflow.modules.financial_core.application.payments.exceptions import (
    DuplicateInternalDepositOperationError,
    InsufficientSourceFundsError,
    InternalDepositBalanceUpdateFailedError,
    InternalDepositLedgerCreationFailedError,
    InternalDepositOutboxEventCreationFailedError,
)
from payflow.modules.financial_core.application.payments.use_cases import (
    InternalDepositUseCase,
)
from payflow.modules.financial_core.domain.ledger import (
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
)
from payflow.modules.financial_core.domain.wallets import BalanceProjection, Wallet
from payflow.modules.financial_core.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
    OutboxEventModel,
    WalletBalanceModel,
)
from payflow.modules.financial_core.infrastructure.repositories.ledger import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.outbox import (
    SQLAlchemyOutboxEventRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.wallets import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.financial_core.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


class FailingTargetSaveWalletBalanceRepository(SQLAlchemyWalletBalanceRepository):
    """Имитирует сбой сохранения target balance внутри БД-транзакции."""

    def __init__(self, session: AsyncSession, *, failed_wallet_id: UUID) -> None:
        """Создает repository с заданным failing wallet.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
            failed_wallet_id: Wallet id, на сохранении которого нужен сбой.
        """
        super().__init__(session)
        self._failed_wallet_id = failed_wallet_id

    async def save(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет balance или выбрасывает RuntimeError для target wallet.

        Args:
            balance: Проекция баланса.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            RuntimeError: Если сохраняется failing wallet.
        """
        if balance.wallet_id == self._failed_wallet_id:
            raise RuntimeError("Forced target balance save failure.")
        return await super().save(balance)


class FailingLedgerTransactionRepository(SQLAlchemyLedgerTransactionRepository):
    """Имитирует сбой создания ledger transaction."""

    async def create(self, transaction: LedgerTransaction) -> LedgerTransaction:
        """Выбрасывает RuntimeError вместо сохранения ledger transaction.

        Args:
            transaction: Доменная ledger transaction.

        Returns:
            Сохраненная ledger transaction.

        Raises:
            RuntimeError: Всегда, чтобы проверить rollback операции.
        """
        raise RuntimeError("Forced internal deposit ledger failure.")


class FailingOutboxEventRepository(SQLAlchemyOutboxEventRepository):
    """Имитирует сбой сохранения outbox event."""

    async def create(self, event: OutboxEventData) -> OutboxEventRecord:
        """Выбрасывает RuntimeError вместо сохранения outbox event.

        Args:
            event: Данные события для записи.

        Returns:
            Сохраненная строка outbox_events.

        Raises:
            RuntimeError: Всегда, чтобы проверить rollback операции.
        """
        raise RuntimeError("Forced internal deposit outbox failure.")


class StaleDuplicateCheckLedgerTransactionRepository(
    SQLAlchemyLedgerTransactionRepository
):
    """Имитирует промах application-level duplicate check."""

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Всегда сообщает, что ledger transaction с operation_id отсутствует.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            False, чтобы тест дошел до database-level unique constraint.
        """
        return False


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для integration-теста payments.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Созданный пользователь.
    """
    users = SQLAlchemyUserRepository(async_session)
    return await users.create(User(email=f"{uuid4()}@example.com"))


async def create_wallet_with_balance(
    async_session: AsyncSession,
    *,
    currency: str = "USD",
    available_amount_minor: int = 0,
) -> Wallet:
    """Создает кошелек с начальной проекцией баланса.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        currency: Код валюты кошелька.
        available_amount_minor: Начальный доступный баланс.

    Returns:
        Созданный кошелек.
    """
    user = await create_user(async_session)
    wallets = SQLAlchemyWalletRepository(async_session)
    balances = SQLAlchemyWalletBalanceRepository(async_session)
    wallet = await wallets.create(Wallet(user_id=user.id, currency=currency))
    await balances.create_initial(
        BalanceProjection(
            wallet_id=wallet.id,
            currency=wallet.currency,
            available_amount_minor=available_amount_minor,
        )
    )
    return wallet


def make_use_case(async_session: AsyncSession) -> InternalDepositUseCase:
    """Создает use case internal deposit с SQLAlchemy dependencies.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case internal deposit.
    """
    return InternalDepositUseCase(
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=SQLAlchemyWalletBalanceRepository(async_session),
        ledger_transactions=SQLAlchemyLedgerTransactionRepository(async_session),
        outbox_events=SQLAlchemyOutboxEventRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


def make_use_case_with_failing_balance_save(
    async_session: AsyncSession,
    *,
    failed_wallet_id: UUID,
) -> InternalDepositUseCase:
    """Создает use case со сбоем сохранения target balance.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        failed_wallet_id: Wallet id, на сохранении которого нужен сбой.

    Returns:
        Use case internal deposit.
    """
    return InternalDepositUseCase(
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=FailingTargetSaveWalletBalanceRepository(
            async_session,
            failed_wallet_id=failed_wallet_id,
        ),
        ledger_transactions=SQLAlchemyLedgerTransactionRepository(async_session),
        outbox_events=SQLAlchemyOutboxEventRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


def make_use_case_with_failing_ledger_create(
    async_session: AsyncSession,
) -> InternalDepositUseCase:
    """Создает use case со сбоем создания ledger transaction.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case internal deposit.
    """
    return InternalDepositUseCase(
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=SQLAlchemyWalletBalanceRepository(async_session),
        ledger_transactions=FailingLedgerTransactionRepository(async_session),
        outbox_events=SQLAlchemyOutboxEventRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


def make_use_case_with_failing_outbox_create(
    async_session: AsyncSession,
) -> InternalDepositUseCase:
    """Создает use case со сбоем создания outbox event.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case internal deposit.
    """
    return InternalDepositUseCase(
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=SQLAlchemyWalletBalanceRepository(async_session),
        ledger_transactions=SQLAlchemyLedgerTransactionRepository(async_session),
        outbox_events=FailingOutboxEventRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


def make_use_case_with_stale_duplicate_check(
    async_session: AsyncSession,
) -> InternalDepositUseCase:
    """Создает use case с промахом duplicate check ledger repository.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case internal deposit.
    """
    return InternalDepositUseCase(
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=SQLAlchemyWalletBalanceRepository(async_session),
        ledger_transactions=StaleDuplicateCheckLedgerTransactionRepository(
            async_session
        ),
        outbox_events=SQLAlchemyOutboxEventRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


async def count_ledger_transactions(async_session: AsyncSession) -> int:
    """Считает ledger transactions в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество ledger transactions.
    """
    return int(
        await async_session.scalar(
            select(func.count()).select_from(LedgerTransactionModel)
        )
        or 0
    )


async def count_ledger_entries(async_session: AsyncSession) -> int:
    """Считает ledger entries в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество ledger entries.
    """
    return int(
        await async_session.scalar(select(func.count()).select_from(LedgerEntryModel))
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


async def get_available_balance(
    async_session: AsyncSession,
    wallet_id: UUID,
) -> int:
    """Возвращает доступный баланс кошелька из БД.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        wallet_id: Идентификатор кошелька.

    Returns:
        Доступная сумма в минорных единицах.
    """
    balance = await async_session.get(WalletBalanceModel, wallet_id)
    assert balance is not None
    return balance.available_amount_minor


async def test_successful_internal_deposit_persists_transaction_and_entries(
    async_session: AsyncSession,
) -> None:
    """Проверяет сохранение ledger transaction и entries.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    target_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=25,
    )
    await async_session.commit()
    operation_id = uuid4()

    result = await make_use_case(async_session).execute(
        operation_id=operation_id,
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=250,
        currency="usd",
    )

    stored_transaction = await async_session.get(
        LedgerTransactionModel,
        result.transaction.id,
    )
    stored_entries = (
        await async_session.scalars(
            select(LedgerEntryModel)
            .where(LedgerEntryModel.transaction_id == result.transaction.id)
            .order_by(LedgerEntryModel.direction)
        )
    ).all()
    assert stored_transaction is not None
    assert stored_transaction.operation_id == operation_id
    assert stored_transaction.operation_type == LedgerOperationType.INTERNAL_DEPOSIT
    assert len(stored_entries) == 2
    assert {
        (entry.wallet_id, entry.direction, entry.amount_minor, entry.currency)
        for entry in stored_entries
    } == {
        (source_wallet.id, LedgerEntryDirection.DEBIT.value, 250, "USD"),
        (target_wallet.id, LedgerEntryDirection.CREDIT.value, 250, "USD"),
    }


async def test_successful_internal_deposit_creates_completed_outbox_event(
    async_session: AsyncSession,
) -> None:
    """Проверяет создание outbox event для успешного internal deposit.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    target_wallet = await create_wallet_with_balance(async_session)
    await async_session.commit()
    operation_id = uuid4()

    result = await make_use_case(async_session).execute(
        operation_id=operation_id,
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=250,
        currency="usd",
    )
    event = await async_session.scalar(
        select(OutboxEventModel).where(
            OutboxEventModel.event_type == "internal_deposit.completed",
        )
    )

    assert event is not None
    assert event.aggregate_type == "internal_deposit"
    assert event.aggregate_id == str(operation_id)
    assert event.payload["operation_id"] == str(operation_id)
    assert event.payload["source_wallet_id"] == str(source_wallet.id)
    assert event.payload["target_wallet_id"] == str(target_wallet.id)
    assert event.payload["ledger_transaction_id"] == str(result.transaction.id)
    assert event.payload["amount_minor"] == 250
    assert event.payload["currency"] == "USD"


async def test_successful_internal_deposit_updates_balances(
    async_session: AsyncSession,
) -> None:
    """Проверяет обновление source и target balance.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    target_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=25,
    )
    await async_session.commit()

    await make_use_case(async_session).execute(
        operation_id=uuid4(),
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=250,
        currency="USD",
    )

    assert await get_available_balance(async_session, source_wallet.id) == 750
    assert await get_available_balance(async_session, target_wallet.id) == 275


async def test_duplicate_operation_id_is_rejected(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ для повторного operation_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    target_wallet = await create_wallet_with_balance(async_session)
    await async_session.commit()
    operation_id = uuid4()
    use_case = make_use_case(async_session)
    await use_case.execute(
        operation_id=operation_id,
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=100,
        currency="USD",
    )

    with pytest.raises(DuplicateInternalDepositOperationError):
        await use_case.execute(
            operation_id=operation_id,
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_ledger_transactions(async_session) == 1
    assert await count_ledger_entries(async_session) == 2
    assert (
        await count_outbox_events(
            async_session,
            event_type="internal_deposit.completed",
        )
        == 1
    )
    assert await get_available_balance(async_session, source_wallet.id) == 900
    assert await get_available_balance(async_session, target_wallet.id) == 100


async def test_database_duplicate_operation_id_is_wrapped_without_side_effects(
    async_session: AsyncSession,
) -> None:
    """Проверяет managed duplicate error при срабатывании DB unique constraint.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    target_wallet = await create_wallet_with_balance(async_session)
    await async_session.commit()
    operation_id = uuid4()
    await make_use_case(async_session).execute(
        operation_id=operation_id,
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=100,
        currency="USD",
    )

    with pytest.raises(DuplicateInternalDepositOperationError):
        await make_use_case_with_stale_duplicate_check(async_session).execute(
            operation_id=operation_id,
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_ledger_transactions(async_session) == 1
    assert await count_ledger_entries(async_session) == 2
    assert (
        await count_outbox_events(
            async_session,
            event_type="internal_deposit.completed",
        )
        == 1
    )
    assert await get_available_balance(async_session, source_wallet.id) == 900
    assert await get_available_balance(async_session, target_wallet.id) == 100


async def test_insufficient_source_funds_does_not_create_ledger_transaction(
    async_session: AsyncSession,
) -> None:
    """Проверяет, что отказ по средствам не создает ledger transaction.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=99,
    )
    target_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=20,
    )
    await async_session.commit()

    with pytest.raises(InsufficientSourceFundsError):
        await make_use_case(async_session).execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
    assert (
        await count_outbox_events(
            async_session,
            event_type="internal_deposit.completed",
        )
        == 0
    )
    assert await get_available_balance(async_session, source_wallet.id) == 99
    assert await get_available_balance(async_session, target_wallet.id) == 20


async def test_failed_ledger_creation_rolls_back_internal_deposit(
    async_session: AsyncSession,
) -> None:
    """Проверяет managed error и rollback при сбое создания ledger transaction.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=500,
    )
    target_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=10,
    )
    await async_session.commit()

    with pytest.raises(InternalDepositLedgerCreationFailedError):
        await make_use_case_with_failing_ledger_create(async_session).execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    async_session.expire_all()
    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
    assert (
        await count_outbox_events(
            async_session,
            event_type="internal_deposit.completed",
        )
        == 0
    )
    assert await get_available_balance(async_session, source_wallet.id) == 500
    assert await get_available_balance(async_session, target_wallet.id) == 10


async def test_failed_operation_rolls_back_partial_balance_updates(
    async_session: AsyncSession,
) -> None:
    """Проверяет managed error и rollback при сбое после source update.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=500,
    )
    target_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=10,
    )
    await async_session.commit()

    with pytest.raises(InternalDepositBalanceUpdateFailedError):
        await make_use_case_with_failing_balance_save(
            async_session,
            failed_wallet_id=target_wallet.id,
        ).execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    async_session.expire_all()
    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
    assert (
        await count_outbox_events(
            async_session,
            event_type="internal_deposit.completed",
        )
        == 0
    )
    assert await get_available_balance(async_session, source_wallet.id) == 500
    assert await get_available_balance(async_session, target_wallet.id) == 10


async def test_failed_outbox_creation_rolls_back_internal_deposit(
    async_session: AsyncSession,
) -> None:
    """Проверяет managed error и rollback при сбое создания outbox event.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    source_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=500,
    )
    target_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=10,
    )
    await async_session.commit()

    with pytest.raises(InternalDepositOutboxEventCreationFailedError):
        await make_use_case_with_failing_outbox_create(async_session).execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    async_session.expire_all()
    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
    assert (
        await count_outbox_events(
            async_session,
            event_type="internal_deposit.completed",
        )
        == 0
    )
    assert await get_available_balance(async_session, source_wallet.id) == 500
    assert await get_available_balance(async_session, target_wallet.id) == 10
