"""SQLAlchemy-репозиторий ledger transaction и immutable entries."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.financial_core.application.ledger.exceptions import (
    LedgerTransactionAlreadyExistsError,
)
from payflow.modules.financial_core.application.ledger.repositories import (
    LedgerTransactionRepository,
)
from payflow.modules.financial_core.domain.ledger import LedgerEntry, LedgerTransaction
from payflow.modules.financial_core.infrastructure.mappers.ledger import (
    ledger_entry_entity_to_model,
    ledger_entry_model_to_entity,
    ledger_transaction_entity_to_model,
    ledger_transaction_model_to_entity,
)
from payflow.modules.financial_core.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
)

_LEDGER_OPERATION_ID_UNIQUE_CONSTRAINT = "uq_ledger_transactions_operation_id"


def _violates_constraint(error: IntegrityError, constraint_name: str) -> bool:
    original_error = error.orig
    diagnostic = getattr(original_error, "diag", None)
    diagnostic_constraint = getattr(diagnostic, "constraint_name", None)
    if (
        isinstance(diagnostic_constraint, str)
        and diagnostic_constraint == constraint_name
    ):
        return True
    return constraint_name in str(original_error) or constraint_name in str(error)


class SQLAlchemyLedgerTransactionRepository(LedgerTransactionRepository):
    """Работает с ledger records через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий ledger transaction.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, transaction: LedgerTransaction) -> LedgerTransaction:
        """Сохраняет ledger transaction вместе с entries в одной БД-транзакции.

        Args:
            transaction: Доменная ledger transaction с immutable entries.

        Returns:
            Сохраненная ledger transaction.

        Raises:
            LedgerTransactionAlreadyExistsError: Если operation_id уже существует.
            sqlalchemy.exc.IntegrityError: Если база данных отклоняет другие
                ограничения.
        """
        transaction_model = ledger_transaction_entity_to_model(transaction)
        entry_models = [
            ledger_entry_entity_to_model(entry) for entry in transaction.entries
        ]

        self._session.add(transaction_model)
        try:
            await self._session.flush()
            self._session.add_all(entry_models)
            await self._session.flush()
        except IntegrityError as exc:
            if _violates_constraint(
                exc,
                _LEDGER_OPERATION_ID_UNIQUE_CONSTRAINT,
            ):
                raise LedgerTransactionAlreadyExistsError(
                    "Ledger transaction with this operation_id already exists."
                ) from exc
            raise

        return ledger_transaction_model_to_entity(transaction_model, entry_models)

    async def get_by_id(self, transaction_id: UUID) -> LedgerTransaction | None:
        """Возвращает ledger transaction по идентификатору.

        Args:
            transaction_id: Идентификатор ledger transaction.

        Returns:
            Ledger transaction или None, если запись не найдена.
        """
        transaction_model = await self._session.get(
            LedgerTransactionModel,
            transaction_id,
        )
        if transaction_model is None:
            return None

        entry_models = await self._get_entry_models_by_transaction_id(transaction_id)
        return ledger_transaction_model_to_entity(transaction_model, entry_models)

    async def get_by_operation_id(
        self,
        operation_id: UUID,
    ) -> LedgerTransaction | None:
        """Возвращает ledger transaction по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            Ledger transaction или None, если запись не найдена.
        """
        statement = select(LedgerTransactionModel).where(
            LedgerTransactionModel.operation_id == operation_id,
        )
        transaction_model = await self._session.scalar(statement)
        if transaction_model is None:
            return None

        entry_models = await self._get_entry_models_by_transaction_id(
            transaction_model.id,
        )
        return ledger_transaction_model_to_entity(transaction_model, entry_models)

    async def get_entries_by_wallet_id(self, wallet_id: UUID) -> list[LedgerEntry]:
        """Возвращает ledger entries по идентификатору кошелька.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Список immutable ledger entries кошелька.
        """
        statement = (
            select(LedgerEntryModel)
            .where(LedgerEntryModel.wallet_id == wallet_id)
            .order_by(LedgerEntryModel.created_at, LedgerEntryModel.id)
        )
        result = await self._session.scalars(statement)
        return [
            ledger_entry_model_to_entity(entry_model) for entry_model in result.all()
        ]

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет существование ledger transaction по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если ledger transaction найдена.
        """
        statement = select(
            exists().where(LedgerTransactionModel.operation_id == operation_id),
        )
        return bool(await self._session.scalar(statement))

    async def _get_entry_models_by_transaction_id(
        self,
        transaction_id: UUID,
    ) -> list[LedgerEntryModel]:
        statement = (
            select(LedgerEntryModel)
            .where(LedgerEntryModel.transaction_id == transaction_id)
            .order_by(LedgerEntryModel.created_at, LedgerEntryModel.id)
        )
        result = await self._session.scalars(statement)
        return list(result.all())
