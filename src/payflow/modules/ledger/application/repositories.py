"""Интерфейсы репозиториев для ledger transaction и entries."""

from typing import Protocol
from uuid import UUID

from payflow.modules.ledger.domain import LedgerEntry, LedgerTransaction


class LedgerTransactionRepository(Protocol):
    """Определяет контракт хранилища ledger transaction для application layer."""

    async def create(self, transaction: LedgerTransaction) -> LedgerTransaction:
        """Сохраняет ledger transaction вместе с immutable entries.

        Args:
            transaction: Доменная ledger transaction с entries.

        Returns:
            Сохраненная ledger transaction.
        """

    async def get_by_id(self, transaction_id: UUID) -> LedgerTransaction | None:
        """Возвращает ledger transaction по идентификатору.

        Args:
            transaction_id: Идентификатор ledger transaction.

        Returns:
            Ledger transaction или None, если запись не найдена.
        """

    async def get_by_operation_id(
        self,
        operation_id: UUID,
    ) -> LedgerTransaction | None:
        """Возвращает ledger transaction по идентификатору бизнес-операции.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            Ledger transaction или None, если запись не найдена.
        """

    async def get_entries_by_wallet_id(self, wallet_id: UUID) -> list[LedgerEntry]:
        """Возвращает immutable ledger entries по идентификатору кошелька.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Список ledger entries кошелька.
        """

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет существование ledger transaction по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если ledger transaction найдена.
        """
