"""Мапперы между доменными P2P-переводами и SQLAlchemy-моделями."""

from payflow.modules.transfers.domain import Transfer, TransferStatus
from payflow.modules.transfers.infrastructure.models import TransferModel


def transfer_entity_to_model(transfer: Transfer) -> TransferModel:
    """Преобразует доменный P2P-перевод в ORM-модель.

    Args:
        transfer: Доменная сущность перевода.

    Returns:
        SQLAlchemy-модель P2P-перевода.
    """
    return TransferModel(
        id=transfer.id,
        operation_id=transfer.operation_id,
        sender_user_id=transfer.sender_user_id,
        sender_wallet_id=transfer.sender_wallet_id,
        recipient_wallet_id=transfer.recipient_wallet_id,
        amount_minor=transfer.amount_minor,
        currency=transfer.currency,
        status=transfer.status.value,
        ledger_transaction_id=transfer.ledger_transaction_id,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
        failed_at=transfer.failed_at,
    )


def transfer_model_to_entity(transfer_model: TransferModel) -> Transfer:
    """Преобразует ORM-модель P2P-перевода в доменную сущность.

    Args:
        transfer_model: SQLAlchemy-модель P2P-перевода.

    Returns:
        Доменная сущность P2P-перевода.
    """
    return Transfer(
        id=transfer_model.id,
        operation_id=transfer_model.operation_id,
        sender_user_id=transfer_model.sender_user_id,
        sender_wallet_id=transfer_model.sender_wallet_id,
        recipient_wallet_id=transfer_model.recipient_wallet_id,
        amount_minor=transfer_model.amount_minor,
        currency=transfer_model.currency,
        status=TransferStatus(transfer_model.status),
        ledger_transaction_id=transfer_model.ledger_transaction_id,
        created_at=transfer_model.created_at,
        updated_at=transfer_model.updated_at,
        failed_at=transfer_model.failed_at,
    )
