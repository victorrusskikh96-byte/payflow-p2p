"""Application use cases для создания ledger records."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from payflow.modules.financial_core.application.ledger.exceptions import (
    LedgerTransactionAlreadyExistsError,
)
from payflow.modules.financial_core.application.ledger.repositories import (
    LedgerTransactionRepository,
)
from payflow.modules.financial_core.application.ledger.transactions import (
    TransactionManager,
)
from payflow.modules.financial_core.domain.ledger import (
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
)


@dataclass(frozen=True, slots=True)
class PostLedgerEntryCommand:
    """Описывает одну ledger entry для posting transaction."""

    wallet_id: UUID
    direction: LedgerEntryDirection
    amount_minor: int
    currency: str


@dataclass(frozen=True, slots=True)
class PostLedgerTransactionCommand:
    """Описывает команду posting ledger transaction."""

    operation_id: UUID
    operation_type: LedgerOperationType
    entries: tuple[PostLedgerEntryCommand, ...]


class PostLedgerTransactionUseCase:
    """Создает ledger transaction вместе с immutable ledger entries."""

    def __init__(
        self,
        *,
        transactions: LedgerTransactionRepository,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case posting ledger transaction.

        Args:
            transactions: Репозиторий ledger transactions.
            transaction_manager: Менеджер транзакции БД.
        """
        self._transactions = transactions
        self._transaction_manager = transaction_manager

    async def execute(
        self,
        command: PostLedgerTransactionCommand,
    ) -> LedgerTransaction:
        """Создает и сохраняет balanced ledger transaction.

        Args:
            command: Команда с operation_id, operation_type и entries.

        Returns:
            Созданная ledger transaction.

        Raises:
            LedgerTransactionAlreadyExistsError: Если operation_id уже posted.
            InvalidLedgerAmountError: Если сумма entry не больше нуля.
            InvalidLedgerEntriesError: Если entries пустые или некорректные.
            MixedLedgerCurrenciesError: Если entries содержат разные валюты.
            UnbalancedLedgerTransactionError: Если DEBIT и CREDIT суммы не равны.
        """
        async with self._transaction_manager:
            if await self._transactions.exists_by_operation_id(command.operation_id):
                raise LedgerTransactionAlreadyExistsError(
                    "Ledger transaction with this operation_id already exists."
                )

            transaction_id = uuid4()
            transaction = LedgerTransaction(
                id=transaction_id,
                operation_id=command.operation_id,
                operation_type=command.operation_type,
                entries=tuple(
                    LedgerEntry(
                        transaction_id=transaction_id,
                        wallet_id=entry.wallet_id,
                        direction=entry.direction,
                        amount_minor=entry.amount_minor,
                        currency=entry.currency,
                    )
                    for entry in command.entries
                ),
            )

            return await self._transactions.create(transaction)
