"""Unit-тесты use case пользовательского P2P-перевода."""

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from payflow.modules.financial_core.application.events import (
    OutboxEventData,
    OutboxEventRecord,
    OutboxEventStatus,
)
from payflow.modules.financial_core.application.transfers.exceptions import (
    InactiveTransferWalletError,
    InsufficientTransferFundsError,
    RecipientWalletNotFoundError,
    SenderWalletNotFoundError,
    TransferWalletCurrencyMismatchError,
    TransferWalletOwnershipError,
)
from payflow.modules.financial_core.application.transfers.use_cases import (
    CreateP2PTransferUseCase,
)
from payflow.modules.financial_core.domain.ledger import (
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
)
from payflow.modules.financial_core.domain.transfers import (
    DuplicateTransferOperationError,
    InvalidTransferAmountError,
    InvalidTransferCurrencyError,
    SameTransferWalletsError,
    Transfer,
    TransferNotFoundError,
    TransferStatus,
)
from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    Wallet,
    WalletStatus,
)


class InMemoryTransferRepository:
    """Хранит P2P-переводы в памяти для unit-тестов."""

    def __init__(self) -> None:
        """Создает пустой repository переводов."""
        self.transfers_by_id: dict[UUID, Transfer] = {}
        self.transfers_by_operation_id: dict[UUID, Transfer] = {}

    async def create(self, transfer: Transfer) -> Transfer:
        """Сохраняет P2P-перевод.

        Args:
            transfer: Доменная сущность перевода.

        Returns:
            Сохраненный перевод.
        """
        self.transfers_by_id[transfer.id] = transfer
        self.transfers_by_operation_id[transfer.operation_id] = transfer
        return transfer

    async def get_by_id(self, transfer_id: UUID) -> Transfer | None:
        """Возвращает P2P-перевод по id.

        Args:
            transfer_id: Идентификатор перевода.

        Returns:
            P2P-перевод или None.
        """
        return self.transfers_by_id.get(transfer_id)

    async def get_by_operation_id(self, operation_id: UUID) -> Transfer | None:
        """Возвращает P2P-перевод по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            P2P-перевод или None.
        """
        return self.transfers_by_operation_id.get(operation_id)

    async def get_by_sender_user_id(self, sender_user_id: UUID) -> list[Transfer]:
        """Возвращает P2P-переводы отправителя.

        Args:
            sender_user_id: Идентификатор пользователя-отправителя.

        Returns:
            Список P2P-переводов отправителя.
        """
        return [
            transfer
            for transfer in self.transfers_by_id.values()
            if transfer.sender_user_id == sender_user_id
        ]

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет наличие P2P-перевода.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если P2P-перевод найден.
        """
        return operation_id in self.transfers_by_operation_id

    async def save_status(self, transfer: Transfer) -> Transfer:
        """Сохраняет статус и ledger transaction id перевода.

        Args:
            transfer: Доменная сущность перевода.

        Returns:
            Обновленный перевод.

        Raises:
            TransferNotFoundError: Если перевод не найден.
        """
        if transfer.id not in self.transfers_by_id:
            raise TransferNotFoundError("Transfer was not found.")
        self.transfers_by_id[transfer.id] = transfer
        self.transfers_by_operation_id[transfer.operation_id] = transfer
        return transfer


class InMemoryWalletRepository:
    """Хранит кошельки в памяти для unit-тестов."""

    def __init__(self, wallets: list[Wallet]) -> None:
        """Создает repository с заданными кошельками.

        Args:
            wallets: Кошельки, доступные для теста.
        """
        self.wallets = {wallet.id: wallet for wallet in wallets}

    async def create(self, wallet: Wallet) -> Wallet:
        """Сохраняет кошелек в памяти.

        Args:
            wallet: Доменная сущность кошелька.

        Returns:
            Сохраненный кошелек.
        """
        self.wallets[wallet.id] = wallet
        return wallet

    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        """Возвращает кошелек по id.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Кошелек или None.
        """
        return self.wallets.get(wallet_id)

    async def get_by_user_id(self, user_id: UUID) -> list[Wallet]:
        """Возвращает кошельки пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список кошельков пользователя.
        """
        return [wallet for wallet in self.wallets.values() if wallet.user_id == user_id]

    async def get_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> Wallet | None:
        """Возвращает кошелек пользователя в валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты.

        Returns:
            Кошелек или None.
        """
        normalized_currency = currency.strip().upper()
        for wallet in self.wallets.values():
            if wallet.user_id == user_id and wallet.currency == normalized_currency:
                return wallet
        return None

    async def exists_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> bool:
        """Проверяет наличие кошелька пользователя в валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты.

        Returns:
            True, если кошелек существует.
        """
        return await self.get_by_user_id_and_currency(user_id, currency) is not None


class InMemoryWalletBalanceRepository:
    """Хранит проекции балансов в памяти для unit-тестов."""

    def __init__(self, balances: list[BalanceProjection]) -> None:
        """Создает repository с заданными балансами.

        Args:
            balances: Проекции балансов, доступные для теста.
        """
        self.balances = {balance.wallet_id: balance for balance in balances}
        self.locked_wallet_ids: list[UUID] = []

    async def create_initial(
        self,
        balance: BalanceProjection,
    ) -> BalanceProjection:
        """Сохраняет начальную проекцию баланса.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        self.balances[balance.wallet_id] = balance
        return balance

    async def get_by_wallet_id(self, wallet_id: UUID) -> BalanceProjection | None:
        """Возвращает баланс по wallet_id.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Проекция баланса или None.
        """
        return self.balances.get(wallet_id)

    async def get_by_wallet_id_for_update(
        self,
        wallet_id: UUID,
    ) -> BalanceProjection:
        """Возвращает баланс и отмечает row lock.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Проекция баланса.
        """
        self.locked_wallet_ids.append(wallet_id)
        return self.balances[wallet_id]

    async def increase_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Увеличивает доступный баланс.

        Args:
            balance: Проекция баланса.
            amount_minor: Сумма увеличения.

        Returns:
            Обновленная проекция баланса.
        """
        balance.increase_available_amount(amount_minor)
        return await self.save(balance)

    async def decrease_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Уменьшает доступный баланс.

        Args:
            balance: Проекция баланса.
            amount_minor: Сумма уменьшения.

        Returns:
            Обновленная проекция баланса.
        """
        balance.decrease_available_amount(amount_minor)
        return await self.save(balance)

    async def has_sufficient_available_balance(
        self,
        wallet_id: UUID,
        amount_minor: int,
    ) -> bool:
        """Проверяет достаточность доступного баланса.

        Args:
            wallet_id: Идентификатор кошелька.
            amount_minor: Проверяемая сумма.

        Returns:
            True, если средств достаточно.
        """
        return self.balances[wallet_id].has_sufficient_available_balance(amount_minor)

    async def save(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет проекцию баланса.

        Args:
            balance: Обновленная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        self.balances[balance.wallet_id] = balance
        return balance

    async def update(self, balance: BalanceProjection) -> BalanceProjection:
        """Обновляет проекцию баланса.

        Args:
            balance: Обновленная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        return await self.save(balance)


class InMemoryLedgerTransactionRepository:
    """Хранит ledger transactions в памяти для unit-тестов."""

    def __init__(self) -> None:
        """Создает пустой repository."""
        self.created_transactions: list[LedgerTransaction] = []
        self.transactions_by_operation_id: dict[UUID, LedgerTransaction] = {}

    async def create(self, transaction: LedgerTransaction) -> LedgerTransaction:
        """Сохраняет ledger transaction.

        Args:
            transaction: Доменная ledger transaction.

        Returns:
            Сохраненная ledger transaction.
        """
        self.created_transactions.append(transaction)
        self.transactions_by_operation_id[transaction.operation_id] = transaction
        return transaction

    async def get_by_id(self, transaction_id: UUID) -> LedgerTransaction | None:
        """Возвращает ledger transaction по id.

        Args:
            transaction_id: Идентификатор ledger transaction.

        Returns:
            Ledger transaction или None.
        """
        for transaction in self.transactions_by_operation_id.values():
            if transaction.id == transaction_id:
                return transaction
        return None

    async def get_by_operation_id(
        self,
        operation_id: UUID,
    ) -> LedgerTransaction | None:
        """Возвращает ledger transaction по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            Ledger transaction или None.
        """
        return self.transactions_by_operation_id.get(operation_id)

    async def get_entries_by_wallet_id(self, wallet_id: UUID) -> list[LedgerEntry]:
        """Возвращает ledger entries кошелька.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Список ledger entries.
        """
        return [
            entry
            for transaction in self.transactions_by_operation_id.values()
            for entry in transaction.entries
            if entry.wallet_id == wallet_id
        ]

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет существование ledger transaction.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если ledger transaction найдена.
        """
        return operation_id in self.transactions_by_operation_id


class InMemoryOutboxEventRepository:
    """Хранит outbox events в памяти для unit-тестов."""

    def __init__(self) -> None:
        """Создает пустой repository outbox events."""
        self.events_by_id: dict[UUID, OutboxEventRecord] = {}

    async def create(self, event: OutboxEventData) -> OutboxEventRecord:
        """Сохраняет outbox event.

        Args:
            event: Данные события для записи.

        Returns:
            Сохраненная строка outbox_events.
        """
        record = OutboxEventRecord(
            id=event.id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            status=OutboxEventStatus.PENDING,
            occurred_at=event.occurred_at,
            created_at=datetime.now(UTC),
            published_at=None,
            attempts=0,
            last_error=None,
        )
        self.events_by_id[record.id] = record
        return record


class FakeTransactionManager:
    """Имитирует transaction manager для unit-тестов."""

    def __init__(self) -> None:
        """Создает fake transaction manager."""
        self.entered = False
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> None:
        """Помечает начало транзакции."""
        self.entered = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Помечает завершение транзакции.

        Args:
            exc_type: Тип исключения, если оно возникло.
            exc: Экземпляр исключения, если оно есть.
            traceback: Traceback исключения, если оно есть.

        Returns:
            None, чтобы не подавлять исключения.
        """
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return None


def make_wallet(
    *,
    wallet_id: UUID | None = None,
    user_id: UUID | None = None,
    currency: str = "USD",
    status: WalletStatus = WalletStatus.ACTIVE,
) -> Wallet:
    """Создает кошелек для unit-теста.

    Args:
        wallet_id: Явный идентификатор кошелька.
        user_id: Идентификатор владельца кошелька.
        currency: Код валюты кошелька.
        status: Статус кошелька.

    Returns:
        Доменный кошелек.
    """
    return Wallet(
        id=wallet_id,
        user_id=user_id if user_id is not None else uuid4(),
        currency=currency,
        status=status,
    )


def make_use_case(
    *,
    sender_wallet: Wallet | None = None,
    recipient_wallet: Wallet | None = None,
    sender_balance_amount_minor: int = 500,
    recipient_balance_amount_minor: int = 20,
) -> tuple[
    CreateP2PTransferUseCase,
    InMemoryTransferRepository,
    InMemoryLedgerTransactionRepository,
    InMemoryWalletBalanceRepository,
    FakeTransactionManager,
    Wallet,
    Wallet,
]:
    """Создает use case и зависимости для unit-теста.

    Args:
        sender_wallet: Кошелек отправителя.
        recipient_wallet: Кошелек получателя.
        sender_balance_amount_minor: Начальный баланс отправителя.
        recipient_balance_amount_minor: Начальный баланс получателя.

    Returns:
        Use case, repositories, transaction manager и кошельки.
    """
    resolved_sender_wallet = (
        sender_wallet if sender_wallet is not None else make_wallet()
    )
    resolved_recipient_wallet = (
        recipient_wallet if recipient_wallet is not None else make_wallet()
    )
    transfers = InMemoryTransferRepository()
    balances = InMemoryWalletBalanceRepository(
        [
            BalanceProjection(
                wallet_id=resolved_sender_wallet.id,
                currency=resolved_sender_wallet.currency,
                available_amount_minor=sender_balance_amount_minor,
            ),
            BalanceProjection(
                wallet_id=resolved_recipient_wallet.id,
                currency=resolved_recipient_wallet.currency,
                available_amount_minor=recipient_balance_amount_minor,
            ),
        ]
    )
    ledger_transactions = InMemoryLedgerTransactionRepository()
    transaction_manager = FakeTransactionManager()
    use_case = CreateP2PTransferUseCase(
        transfers=transfers,
        wallets=InMemoryWalletRepository(
            [resolved_sender_wallet, resolved_recipient_wallet]
        ),
        balances=balances,
        ledger_transactions=ledger_transactions,
        outbox_events=InMemoryOutboxEventRepository(),
        transaction_manager=transaction_manager,
    )
    return (
        use_case,
        transfers,
        ledger_transactions,
        balances,
        transaction_manager,
        resolved_sender_wallet,
        resolved_recipient_wallet,
    )


async def test_successful_transfer_creates_balanced_ledger_transaction() -> None:
    """Проверяет создание сбалансированной ledger transaction."""
    (
        use_case,
        transfers,
        ledger_transactions,
        _,
        transaction_manager,
        sender_wallet,
        recipient_wallet,
    ) = make_use_case()
    operation_id = uuid4()

    result = await use_case.execute(
        operation_id=operation_id,
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=100,
        currency="usd",
    )

    transaction = result.transaction
    assert transaction.operation_id == operation_id
    assert transaction.operation_type is LedgerOperationType.P2P_TRANSFER
    assert transaction.is_balanced()
    assert ledger_transactions.created_transactions == [transaction]
    assert [
        (entry.wallet_id, entry.direction, entry.amount_minor, entry.currency)
        for entry in transaction.entries
    ] == [
        (sender_wallet.id, LedgerEntryDirection.DEBIT, 100, "USD"),
        (recipient_wallet.id, LedgerEntryDirection.CREDIT, 100, "USD"),
    ]
    assert result.transfer.status is TransferStatus.COMPLETED
    assert result.transfer.ledger_transaction_id == transaction.id
    assert transfers.transfers_by_operation_id[operation_id] == result.transfer
    assert transaction_manager.entered
    assert transaction_manager.committed
    assert not transaction_manager.rolled_back


async def test_successful_transfer_decreases_sender_balance() -> None:
    """Проверяет уменьшение баланса отправителя."""
    use_case, _, _, balances, _, sender_wallet, recipient_wallet = make_use_case(
        sender_balance_amount_minor=500,
        recipient_balance_amount_minor=20,
    )

    result = await use_case.execute(
        operation_id=uuid4(),
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=125,
        currency="USD",
    )

    assert result.sender_balance.available_amount_minor == 375
    assert balances.balances[sender_wallet.id].available_amount_minor == 375


async def test_successful_transfer_increases_recipient_balance() -> None:
    """Проверяет увеличение баланса получателя."""
    use_case, _, _, balances, _, sender_wallet, recipient_wallet = make_use_case(
        sender_balance_amount_minor=500,
        recipient_balance_amount_minor=20,
    )

    result = await use_case.execute(
        operation_id=uuid4(),
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=125,
        currency="USD",
    )

    assert result.recipient_balance.available_amount_minor == 145
    assert balances.balances[recipient_wallet.id].available_amount_minor == 145


@pytest.mark.parametrize(
    ("sender_wallet_id", "recipient_wallet_id"),
    [
        (
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ),
        (
            UUID("00000000-0000-0000-0000-000000000002"),
            UUID("00000000-0000-0000-0000-000000000001"),
        ),
    ],
)
async def test_transfer_locks_balances_by_wallet_id(
    sender_wallet_id: UUID,
    recipient_wallet_id: UUID,
) -> None:
    """Проверяет стабильный порядок locks и корректный результат.

    Args:
        sender_wallet_id: Идентификатор sender wallet.
        recipient_wallet_id: Идентификатор recipient wallet.
    """
    sender_user_id = uuid4()
    sender_wallet = make_wallet(
        wallet_id=sender_wallet_id,
        user_id=sender_user_id,
    )
    recipient_wallet = make_wallet(wallet_id=recipient_wallet_id)
    use_case, _, _, balances, _, _, _ = make_use_case(
        sender_wallet=sender_wallet,
        recipient_wallet=recipient_wallet,
        sender_balance_amount_minor=500,
        recipient_balance_amount_minor=20,
    )

    result = await use_case.execute(
        operation_id=uuid4(),
        sender_user_id=sender_user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=100,
        currency="USD",
    )

    assert balances.locked_wallet_ids == sorted(
        [sender_wallet.id, recipient_wallet.id],
        key=lambda wallet_id: wallet_id.int,
    )
    assert result.sender_balance.available_amount_minor == 400
    assert result.recipient_balance.available_amount_minor == 120
    assert balances.balances[sender_wallet.id].available_amount_minor == 400
    assert balances.balances[recipient_wallet.id].available_amount_minor == 120


async def test_duplicate_operation_id_is_rejected() -> None:
    """Проверяет отказ для повторного operation_id."""
    (
        use_case,
        transfers,
        ledger_transactions,
        balances,
        transaction_manager,
        sender_wallet,
        recipient_wallet,
    ) = make_use_case()
    operation_id = uuid4()
    first_result = await use_case.execute(
        operation_id=operation_id,
        sender_user_id=sender_wallet.user_id,
        sender_wallet_id=sender_wallet.id,
        recipient_wallet_id=recipient_wallet.id,
        amount_minor=100,
        currency="USD",
    )
    transaction_manager.committed = False
    transaction_manager.rolled_back = False

    with pytest.raises(DuplicateTransferOperationError):
        await use_case.execute(
            operation_id=operation_id,
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert list(transfers.transfers_by_operation_id.values()) == [first_result.transfer]
    assert ledger_transactions.created_transactions == [first_result.transaction]
    assert balances.balances[sender_wallet.id].available_amount_minor == 400
    assert balances.balances[recipient_wallet.id].available_amount_minor == 120
    assert transaction_manager.rolled_back


async def test_insufficient_funds_is_rejected() -> None:
    """Проверяет отказ при недостаточном балансе отправителя."""
    (
        use_case,
        transfers,
        ledger_transactions,
        balances,
        transaction_manager,
        sender_wallet,
        recipient_wallet,
    ) = make_use_case(sender_balance_amount_minor=99)

    with pytest.raises(InsufficientTransferFundsError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert transfers.transfers_by_id == {}
    assert ledger_transactions.created_transactions == []
    assert balances.balances[sender_wallet.id].available_amount_minor == 99
    assert balances.balances[recipient_wallet.id].available_amount_minor == 20
    assert transaction_manager.rolled_back


async def test_sender_wallet_belongs_to_another_user_is_rejected() -> None:
    """Проверяет отказ, если sender wallet принадлежит другому пользователю."""
    (
        use_case,
        _,
        ledger_transactions,
        _,
        transaction_manager,
        sender_wallet,
        (recipient_wallet),
    ) = make_use_case()

    with pytest.raises(TransferWalletOwnershipError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=uuid4(),
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


async def test_sender_wallet_not_found_is_rejected() -> None:
    """Проверяет отказ, если sender wallet не найден."""
    (
        use_case,
        transfers,
        ledger_transactions,
        _,
        transaction_manager,
        _,
        recipient_wallet,
    ) = make_use_case()

    with pytest.raises(SenderWalletNotFoundError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=uuid4(),
            sender_wallet_id=uuid4(),
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert transfers.transfers_by_id == {}
    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


async def test_recipient_wallet_not_found_is_rejected() -> None:
    """Проверяет отказ, если recipient wallet не найден."""
    (
        use_case,
        transfers,
        ledger_transactions,
        _,
        transaction_manager,
        sender_wallet,
        _,
    ) = make_use_case()

    with pytest.raises(RecipientWalletNotFoundError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=uuid4(),
            amount_minor=100,
            currency="USD",
        )

    assert transfers.transfers_by_id == {}
    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


async def test_currency_mismatch_is_rejected() -> None:
    """Проверяет отказ при несовпадении валют кошельков."""
    sender_wallet = make_wallet(currency="USD")
    recipient_wallet = make_wallet(currency="EUR")
    use_case, _, ledger_transactions, _, transaction_manager, _, _ = make_use_case(
        sender_wallet=sender_wallet,
        recipient_wallet=recipient_wallet,
    )

    with pytest.raises(TransferWalletCurrencyMismatchError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


async def test_same_wallet_transfer_is_rejected() -> None:
    """Проверяет отказ для перевода на тот же кошелек."""
    use_case, _, ledger_transactions, _, transaction_manager, sender_wallet, _ = (
        make_use_case()
    )

    with pytest.raises(SameTransferWalletsError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=sender_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert not transaction_manager.entered


@pytest.mark.parametrize("status", [WalletStatus.BLOCKED, WalletStatus.CLOSED])
async def test_inactive_sender_wallet_is_rejected(status: WalletStatus) -> None:
    """Проверяет отказ, если sender wallet не ACTIVE.

    Args:
        status: Недоступный статус кошелька.
    """
    sender_wallet = make_wallet(status=status)
    recipient_wallet = make_wallet()
    use_case, _, ledger_transactions, _, transaction_manager, _, _ = make_use_case(
        sender_wallet=sender_wallet,
        recipient_wallet=recipient_wallet,
    )

    with pytest.raises(InactiveTransferWalletError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


@pytest.mark.parametrize("status", [WalletStatus.BLOCKED, WalletStatus.CLOSED])
async def test_inactive_recipient_wallet_is_rejected(status: WalletStatus) -> None:
    """Проверяет отказ, если recipient wallet не ACTIVE.

    Args:
        status: Недоступный статус кошелька.
    """
    sender_wallet = make_wallet()
    recipient_wallet = make_wallet(status=status)
    use_case, _, ledger_transactions, _, transaction_manager, _, _ = make_use_case(
        sender_wallet=sender_wallet,
        recipient_wallet=recipient_wallet,
    )

    with pytest.raises(InactiveTransferWalletError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


@pytest.mark.parametrize("amount_minor", [0, -1])
async def test_non_positive_transfer_amount_is_rejected(
    amount_minor: int,
) -> None:
    """Проверяет отказ для amount_minor <= 0.

    Args:
        amount_minor: Некорректная сумма перевода.
    """
    (
        use_case,
        transfers,
        ledger_transactions,
        _,
        transaction_manager,
        sender_wallet,
        recipient_wallet,
    ) = make_use_case()

    with pytest.raises(InvalidTransferAmountError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=amount_minor,
            currency="USD",
        )

    assert transfers.transfers_by_id == {}
    assert ledger_transactions.created_transactions == []
    assert not transaction_manager.entered


@pytest.mark.parametrize("currency", ["", "   "])
async def test_empty_transfer_currency_is_rejected(currency: str) -> None:
    """Проверяет отказ для пустой валюты перевода.

    Args:
        currency: Некорректная валюта перевода.
    """
    (
        use_case,
        transfers,
        ledger_transactions,
        _,
        transaction_manager,
        sender_wallet,
        recipient_wallet,
    ) = make_use_case()

    with pytest.raises(InvalidTransferCurrencyError):
        await use_case.execute(
            operation_id=uuid4(),
            sender_user_id=sender_wallet.user_id,
            sender_wallet_id=sender_wallet.id,
            recipient_wallet_id=recipient_wallet.id,
            amount_minor=100,
            currency=currency,
        )

    assert transfers.transfers_by_id == {}
    assert ledger_transactions.created_transactions == []
    assert not transaction_manager.entered
