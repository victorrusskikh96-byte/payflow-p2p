"""Интеграционные тесты use case пользовательского P2P-перевода."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.ledger.domain import (
    LedgerEntryDirection,
    LedgerOperationType,
)
from payflow.modules.ledger.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
)
from payflow.modules.ledger.infrastructure.repositories import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.transfers.application.exceptions import (
    InsufficientTransferFundsError,
    TransferWalletCurrencyMismatchError,
    TransferWalletOwnershipError,
)
from payflow.modules.transfers.application.use_cases import CreateP2PTransferUseCase
from payflow.modules.transfers.domain import (
    DuplicateTransferOperationError,
    SameTransferWalletsError,
    TransferStatus,
)
from payflow.modules.transfers.infrastructure.models import TransferModel
from payflow.modules.transfers.infrastructure.repositories import (
    SQLAlchemyTransferRepository,
)
from payflow.modules.transfers.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository
from payflow.modules.wallets.domain import BalanceProjection, Wallet, WalletStatus
from payflow.modules.wallets.infrastructure.models import WalletBalanceModel
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)


class FailingRecipientSaveWalletBalanceRepository(SQLAlchemyWalletBalanceRepository):
    """Имитирует сбой сохранения recipient balance внутри БД-транзакции."""

    def __init__(self, session: AsyncSession, *, failed_wallet_id: UUID) -> None:
        """Создает repository с заданным failing wallet.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
            failed_wallet_id: Wallet id, на сохранении которого нужен сбой.
        """
        super().__init__(session)
        self._failed_wallet_id = failed_wallet_id

    async def save(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет balance или выбрасывает RuntimeError для recipient wallet.

        Args:
            balance: Проекция баланса.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            RuntimeError: Если сохраняется failing wallet.
        """
        if balance.wallet_id == self._failed_wallet_id:
            raise RuntimeError("Forced recipient balance save failure.")
        return await super().save(balance)


async def create_user(async_session: AsyncSession) -> User:
    """Создает пользователя для integration-теста transfers.

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
    user: User | None = None,
    currency: str = "USD",
    status: WalletStatus = WalletStatus.ACTIVE,
    available_amount_minor: int = 0,
) -> Wallet:
    """Создает кошелек с начальной проекцией баланса.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        user: Владелец кошелька или None для создания нового пользователя.
        currency: Код валюты кошелька.
        status: Статус кошелька.
        available_amount_minor: Начальный доступный баланс.

    Returns:
        Созданный кошелек.
    """
    resolved_user = user if user is not None else await create_user(async_session)
    wallets = SQLAlchemyWalletRepository(async_session)
    balances = SQLAlchemyWalletBalanceRepository(async_session)
    wallet = await wallets.create(
        Wallet(user_id=resolved_user.id, currency=currency, status=status)
    )
    await balances.create_initial(
        BalanceProjection(
            wallet_id=wallet.id,
            currency=wallet.currency,
            available_amount_minor=available_amount_minor,
        )
    )
    return wallet


def make_use_case(async_session: AsyncSession) -> CreateP2PTransferUseCase:
    """Создает use case P2P-перевода с SQLAlchemy dependencies.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Use case P2P-перевода.
    """
    return CreateP2PTransferUseCase(
        transfers=SQLAlchemyTransferRepository(async_session),
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=SQLAlchemyWalletBalanceRepository(async_session),
        ledger_transactions=SQLAlchemyLedgerTransactionRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


def make_use_case_with_failing_balance_save(
    async_session: AsyncSession,
    *,
    failed_wallet_id: UUID,
) -> CreateP2PTransferUseCase:
    """Создает use case со сбоем сохранения recipient balance.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
        failed_wallet_id: Wallet id, на сохранении которого нужен сбой.

    Returns:
        Use case P2P-перевода.
    """
    return CreateP2PTransferUseCase(
        transfers=SQLAlchemyTransferRepository(async_session),
        wallets=SQLAlchemyWalletRepository(async_session),
        balances=FailingRecipientSaveWalletBalanceRepository(
            async_session,
            failed_wallet_id=failed_wallet_id,
        ),
        ledger_transactions=SQLAlchemyLedgerTransactionRepository(async_session),
        transaction_manager=SQLAlchemyTransactionManager(async_session),
    )


async def count_transfers(async_session: AsyncSession) -> int:
    """Считает P2P-переводы в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество P2P-переводов.
    """
    return int(
        await async_session.scalar(select(func.count()).select_from(TransferModel))
        or 0
    )


async def count_completed_transfers(async_session: AsyncSession) -> int:
    """Считает completed P2P-переводы в базе данных.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Количество completed P2P-переводов.
    """
    return int(
        await async_session.scalar(
            select(func.count())
            .select_from(TransferModel)
            .where(TransferModel.status == TransferStatus.COMPLETED.value)
        )
        or 0
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


async def test_successful_p2p_transfer_persists_transfer_transaction_and_entries(
    async_session: AsyncSession,
) -> None:
    """Проверяет сохранение transfer, ledger transaction и ledger entries.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    recipient_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=25,
    )
    await async_session.commit()
    operation_id = uuid4()

    result = await make_use_case(async_session).execute(
        operation_id=operation_id,
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=250,
        currency="usd",
    )

    stored_transfer = await async_session.get(TransferModel, result.transfer.id)
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
    assert stored_transfer is not None
    assert stored_transfer.operation_id == operation_id
    assert stored_transfer.status == TransferStatus.COMPLETED.value
    assert stored_transfer.ledger_transaction_id == result.transaction.id
    assert stored_transaction is not None
    assert stored_transaction.operation_id == operation_id
    assert stored_transaction.operation_type == LedgerOperationType.P2P_TRANSFER
    assert len(stored_entries) == 2
    assert {
        (entry.wallet_id, entry.direction, entry.amount_minor, entry.currency)
        for entry in stored_entries
    } == {
        (sender_wallet.id, LedgerEntryDirection.DEBIT.value, 250, "USD"),
        (recipient_wallet.id, LedgerEntryDirection.CREDIT.value, 250, "USD"),
    }


async def test_successful_p2p_transfer_updates_balances(
    async_session: AsyncSession,
) -> None:
    """Проверяет уменьшение sender balance и увеличение recipient balance.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    recipient_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=25,
    )
    await async_session.commit()

    await make_use_case(async_session).execute(
        operation_id=uuid4(),
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=250,
        currency="USD",
    )

    assert await get_available_balance(async_session, sender_wallet.id) == 750
    assert await get_available_balance(async_session, recipient_wallet.id) == 275


async def test_duplicate_operation_id_is_rejected(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ для повторного operation_id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    recipient_wallet = await create_wallet_with_balance(async_session)
    await async_session.commit()
    operation_id = uuid4()
    use_case = make_use_case(async_session)
    await use_case.execute(
        operation_id=operation_id,
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=100,
        currency="USD",
    )

    with pytest.raises(DuplicateTransferOperationError):
        await use_case.execute(
            operation_id=operation_id,
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_transfers(async_session) == 1
    assert await count_ledger_transactions(async_session) == 1
    assert await count_ledger_entries(async_session) == 2
    assert await get_available_balance(async_session, sender_wallet.id) == 900
    assert await get_available_balance(async_session, recipient_wallet.id) == 100


async def test_insufficient_funds_does_not_complete_transfer_or_change_balances(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ по средствам без completed transfer и изменений баланса.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=99,
    )
    recipient_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=20,
    )
    await async_session.commit()

    with pytest.raises(InsufficientTransferFundsError):
        await make_use_case(async_session).execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_completed_transfers(async_session) == 0
    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
    assert await get_available_balance(async_session, sender_wallet.id) == 99
    assert await get_available_balance(async_session, recipient_wallet.id) == 20


async def test_transfer_between_wallets_with_different_currencies_is_rejected(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ для перевода между кошельками разных валют.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        currency="USD",
        available_amount_minor=1_000,
    )
    recipient_wallet = await create_wallet_with_balance(
        async_session,
        currency="EUR",
        available_amount_minor=20,
    )
    await async_session.commit()

    with pytest.raises(TransferWalletCurrencyMismatchError):
        await make_use_case(async_session).execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_transfers(async_session) == 0
    assert await count_ledger_transactions(async_session) == 0
    assert await get_available_balance(async_session, sender_wallet.id) == 1_000
    assert await get_available_balance(async_session, recipient_wallet.id) == 20


async def test_transfer_to_same_wallet_is_rejected(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ для перевода на тот же wallet.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=1_000,
    )
    await async_session.commit()

    with pytest.raises(SameTransferWalletsError):
        await make_use_case(async_session).execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=sender_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_transfers(async_session) == 0
    assert await count_ledger_transactions(async_session) == 0
    assert await get_available_balance(async_session, sender_wallet.id) == 1_000


async def test_sender_cannot_transfer_from_another_users_wallet(
    async_session: AsyncSession,
) -> None:
    """Проверяет отказ отправки с чужого wallet.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    owner = await create_user(async_session)
    attacker = await create_user(async_session)
    sender_wallet = await create_wallet_with_balance(
        async_session,
        user=owner,
        available_amount_minor=1_000,
    )
    recipient_wallet = await create_wallet_with_balance(async_session)
    await async_session.commit()

    with pytest.raises(TransferWalletOwnershipError):
        await make_use_case(async_session).execute(
            operation_id=uuid4(),
            sender_user_id=attacker.id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert await count_transfers(async_session) == 0
    assert await count_ledger_transactions(async_session) == 0
    assert await get_available_balance(async_session, sender_wallet.id) == 1_000
    assert await get_available_balance(async_session, recipient_wallet.id) == 0


async def test_partial_updates_are_rolled_back_on_error(
    async_session: AsyncSession,
) -> None:
    """Проверяет rollback transfer, ledger и balances при частичном сбое.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    sender_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=500,
    )
    recipient_wallet = await create_wallet_with_balance(
        async_session,
        available_amount_minor=10,
    )
    await async_session.commit()

    with pytest.raises(RuntimeError, match="Forced recipient balance save failure"):
        await make_use_case_with_failing_balance_save(
            async_session,
            failed_wallet_id=recipient_wallet.id,
        ).execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    async_session.expire_all()
    assert await count_transfers(async_session) == 0
    assert await count_ledger_transactions(async_session) == 0
    assert await count_ledger_entries(async_session) == 0
    assert await get_available_balance(async_session, sender_wallet.id) == 500
    assert await get_available_balance(async_session, recipient_wallet.id) == 10
