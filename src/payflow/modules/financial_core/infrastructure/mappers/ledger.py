"""Мапперы между доменными объектами ledger и SQLAlchemy-моделями."""

from collections.abc import Sequence

from payflow.modules.financial_core.domain.ledger import (
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
    LedgerTransactionStatus,
)
from payflow.modules.financial_core.infrastructure.models import (
    LedgerEntryModel,
    LedgerTransactionModel,
)


def ledger_transaction_entity_to_model(
    transaction: LedgerTransaction,
) -> LedgerTransactionModel:
    """Преобразует доменную ledger transaction в ORM-модель.

    Args:
        transaction: Доменная ledger transaction.

    Returns:
        SQLAlchemy-модель ledger transaction.
    """
    return LedgerTransactionModel(
        id=transaction.id,
        operation_id=transaction.operation_id,
        operation_type=transaction.operation_type.value,
        status=transaction.status.value,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


def ledger_entry_entity_to_model(entry: LedgerEntry) -> LedgerEntryModel:
    """Преобразует доменную ledger entry в ORM-модель.

    Args:
        entry: Доменная ledger entry.

    Returns:
        SQLAlchemy-модель ledger entry.
    """
    return LedgerEntryModel(
        id=entry.id,
        transaction_id=entry.transaction_id,
        wallet_id=entry.wallet_id,
        direction=entry.direction.value,
        amount_minor=entry.amount_minor,
        currency=entry.currency,
        created_at=entry.created_at,
    )


def ledger_entry_model_to_entity(entry_model: LedgerEntryModel) -> LedgerEntry:
    """Преобразует ORM-модель ledger entry в доменную сущность.

    Args:
        entry_model: SQLAlchemy-модель ledger entry.

    Returns:
        Доменная ledger entry.
    """
    return LedgerEntry(
        id=entry_model.id,
        transaction_id=entry_model.transaction_id,
        wallet_id=entry_model.wallet_id,
        direction=LedgerEntryDirection(entry_model.direction),
        amount_minor=entry_model.amount_minor,
        currency=entry_model.currency,
        created_at=entry_model.created_at,
    )


def ledger_transaction_model_to_entity(
    transaction_model: LedgerTransactionModel,
    entry_models: Sequence[LedgerEntryModel],
) -> LedgerTransaction:
    """Преобразует ORM-модель ledger transaction в доменную сущность.

    Args:
        transaction_model: SQLAlchemy-модель ledger transaction.
        entry_models: ORM-модели entries этой ledger transaction.

    Returns:
        Доменная ledger transaction с immutable entries.
    """
    return LedgerTransaction(
        id=transaction_model.id,
        operation_id=transaction_model.operation_id,
        operation_type=LedgerOperationType(transaction_model.operation_type),
        status=LedgerTransactionStatus(transaction_model.status),
        created_at=transaction_model.created_at,
        updated_at=transaction_model.updated_at,
        entries=tuple(
            ledger_entry_model_to_entity(entry_model) for entry_model in entry_models
        ),
    )
