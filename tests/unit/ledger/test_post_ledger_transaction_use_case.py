"""Unit-тесты use case posting ledger transaction."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from payflow.modules.financial_core.application.ledger.exceptions import (
    LedgerTransactionAlreadyExistsError,
)
from payflow.modules.financial_core.application.ledger.use_cases import (
    PostLedgerEntryCommand,
    PostLedgerTransactionCommand,
    PostLedgerTransactionUseCase,
)
from payflow.modules.financial_core.domain.ledger import (
    InvalidLedgerAmountError,
    InvalidLedgerEntriesError,
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
    MixedLedgerCurrenciesError,
    UnbalancedLedgerTransactionError,
)


class InMemoryLedgerTransactionRepository:
    """Хранит ledger transactions в памяти для unit-тестов."""

    def __init__(self) -> None:
        """Создает пустой in-memory repository."""
        self.created_transactions: list[LedgerTransaction] = []
        self.transactions_by_operation_id: dict[UUID, LedgerTransaction] = {}

    async def create(self, transaction: LedgerTransaction) -> LedgerTransaction:
        """Сохраняет ledger transaction в памяти.

        Args:
            transaction: Доменная ledger transaction.

        Returns:
            Сохраненная ledger transaction.
        """
        self.created_transactions.append(transaction)
        self.transactions_by_operation_id[transaction.operation_id] = transaction
        return transaction

    async def get_by_id(self, transaction_id: UUID) -> LedgerTransaction | None:
        """Возвращает ledger transaction по идентификатору.

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
        """Возвращает ledger entries по wallet_id.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Список ledger entries кошелька.
        """
        return [
            entry
            for transaction in self.transactions_by_operation_id.values()
            for entry in transaction.entries
            if entry.wallet_id == wallet_id
        ]

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет наличие ledger transaction по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если ledger transaction найдена.
        """
        return operation_id in self.transactions_by_operation_id


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
            traceback: Traceback исключения, если он есть.

        Returns:
            None, чтобы не подавлять исключения.
        """
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return None


def make_post_command(
    *,
    operation_id: UUID | None = None,
    debit_amount_minor: int = 100,
    credit_amount_minor: int = 100,
    debit_currency: str = "USD",
    credit_currency: str = "USD",
    entries: tuple[PostLedgerEntryCommand, ...] | None = None,
) -> PostLedgerTransactionCommand:
    """Создает команду posting ledger transaction для тестов.

    Args:
        operation_id: Идентификатор бизнес-операции.
        debit_amount_minor: Сумма DEBIT entry.
        credit_amount_minor: Сумма CREDIT entry.
        debit_currency: Валюта DEBIT entry.
        credit_currency: Валюта CREDIT entry.
        entries: Явный список entries для команды.

    Returns:
        Команда posting ledger transaction.
    """
    resolved_entries = entries
    if resolved_entries is None:
        resolved_entries = (
            PostLedgerEntryCommand(
                wallet_id=uuid4(),
                direction=LedgerEntryDirection.DEBIT,
                amount_minor=debit_amount_minor,
                currency=debit_currency,
            ),
            PostLedgerEntryCommand(
                wallet_id=uuid4(),
                direction=LedgerEntryDirection.CREDIT,
                amount_minor=credit_amount_minor,
                currency=credit_currency,
            ),
        )

    return PostLedgerTransactionCommand(
        operation_id=operation_id if operation_id is not None else uuid4(),
        operation_type=LedgerOperationType.P2P_TRANSFER,
        entries=resolved_entries,
    )


def make_use_case() -> tuple[
    PostLedgerTransactionUseCase,
    InMemoryLedgerTransactionRepository,
    FakeTransactionManager,
]:
    """Создает use case с in-memory dependencies.

    Returns:
        Use case, repository и transaction manager.
    """
    repository = InMemoryLedgerTransactionRepository()
    transaction_manager = FakeTransactionManager()
    use_case = PostLedgerTransactionUseCase(
        transactions=repository,
        transaction_manager=transaction_manager,
    )
    return use_case, repository, transaction_manager


async def test_posts_balanced_ledger_transaction() -> None:
    """Проверяет успешный posting balanced ledger transaction."""
    use_case, repository, transaction_manager = make_use_case()
    command = make_post_command()

    transaction = await use_case.execute(command)

    assert transaction.operation_id == command.operation_id
    assert transaction.operation_type is command.operation_type
    assert transaction.is_balanced()
    assert len(transaction.entries) == 2
    assert {entry.transaction_id for entry in transaction.entries} == {transaction.id}
    assert repository.created_transactions == [transaction]
    assert transaction_manager.entered
    assert transaction_manager.committed
    assert not transaction_manager.rolled_back


async def test_rejects_unbalanced_ledger_transaction() -> None:
    """Проверяет отказ для unbalanced ledger transaction."""
    use_case, repository, transaction_manager = make_use_case()
    command = make_post_command(credit_amount_minor=90)

    with pytest.raises(UnbalancedLedgerTransactionError):
        await use_case.execute(command)

    assert repository.created_transactions == []
    assert transaction_manager.rolled_back


async def test_rejects_mixed_currencies() -> None:
    """Проверяет отказ для ledger transaction с разными валютами."""
    use_case, repository, transaction_manager = make_use_case()
    command = make_post_command(credit_currency="EUR")

    with pytest.raises(MixedLedgerCurrenciesError):
        await use_case.execute(command)

    assert repository.created_transactions == []
    assert transaction_manager.rolled_back


async def test_rejects_duplicate_operation_id() -> None:
    """Проверяет отказ для duplicate operation_id."""
    use_case, repository, transaction_manager = make_use_case()
    operation_id = uuid4()
    existing_transaction = await use_case.execute(
        make_post_command(operation_id=operation_id)
    )
    transaction_manager.committed = False
    transaction_manager.rolled_back = False

    with pytest.raises(LedgerTransactionAlreadyExistsError):
        await use_case.execute(make_post_command(operation_id=operation_id))

    assert repository.created_transactions == [existing_transaction]
    assert transaction_manager.rolled_back


@pytest.mark.parametrize("amount_minor", [0, -1])
async def test_rejects_non_positive_entry_amount(amount_minor: int) -> None:
    """Проверяет отказ для entries с amount_minor <= 0.

    Args:
        amount_minor: Неположительная сумма entry.
    """
    use_case, repository, transaction_manager = make_use_case()
    command = make_post_command(debit_amount_minor=amount_minor)

    with pytest.raises(InvalidLedgerAmountError):
        await use_case.execute(command)

    assert repository.created_transactions == []
    assert transaction_manager.rolled_back


async def test_rejects_empty_entries() -> None:
    """Проверяет отказ для пустого списка entries."""
    use_case, repository, transaction_manager = make_use_case()
    command = make_post_command(entries=())

    with pytest.raises(InvalidLedgerEntriesError):
        await use_case.execute(command)

    assert repository.created_transactions == []
    assert transaction_manager.rolled_back
