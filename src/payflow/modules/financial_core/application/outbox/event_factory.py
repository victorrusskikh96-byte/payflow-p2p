"""Фабрика application-level событий для сохранения в outbox."""

from datetime import UTC, datetime
from uuid import UUID

from payflow.modules.financial_core.domain.outbox import (
    InvalidOutboxEventError,
    OutboxEvent,
)


class OutboxEventFactory:
    """Создает outbox events для доменных операций приложения."""

    @staticmethod
    def wallet_created(
        *,
        wallet_id: UUID,
        user_id: UUID,
        currency: str,
        occurred_at: datetime | None = None,
    ) -> OutboxEvent:
        """Создает событие wallet.created.

        Args:
            wallet_id: Идентификатор созданного кошелька.
            user_id: Идентификатор владельца кошелька.
            currency: Валюта кошелька.
            occurred_at: Момент возникновения события.

        Returns:
            Outbox event с JSON-safe payload.

        Raises:
            InvalidOutboxEventError: Если currency пустая после нормализации.
        """
        event_time = _resolve_occurred_at(occurred_at)
        normalized_currency = _normalize_currency(currency)
        return OutboxEvent(
            event_type="wallet.created",
            aggregate_type="wallet",
            aggregate_id=wallet_id,
            occurred_at=event_time,
            payload={
                "wallet_id": str(wallet_id),
                "user_id": str(user_id),
                "currency": normalized_currency,
                "occurred_at": _serialize_datetime(event_time),
            },
        )

    @staticmethod
    def internal_deposit_completed(
        *,
        operation_id: UUID,
        source_wallet_id: UUID,
        target_wallet_id: UUID,
        ledger_transaction_id: UUID,
        amount_minor: int,
        currency: str,
        occurred_at: datetime | None = None,
    ) -> OutboxEvent:
        """Создает событие internal_deposit.completed.

        Args:
            operation_id: Идентификатор операции internal deposit.
            source_wallet_id: Идентификатор funding wallet.
            target_wallet_id: Идентификатор пополняемого кошелька.
            ledger_transaction_id: Идентификатор ledger transaction.
            amount_minor: Сумма операции в минорных единицах.
            currency: Валюта операции.
            occurred_at: Момент возникновения события.

        Returns:
            Outbox event с JSON-safe payload.

        Raises:
            InvalidOutboxEventError: Если currency пустая после нормализации.
        """
        event_time = _resolve_occurred_at(occurred_at)
        normalized_currency = _normalize_currency(currency)
        return OutboxEvent(
            event_type="internal_deposit.completed",
            aggregate_type="internal_deposit",
            aggregate_id=operation_id,
            occurred_at=event_time,
            payload={
                "operation_id": str(operation_id),
                "source_wallet_id": str(source_wallet_id),
                "target_wallet_id": str(target_wallet_id),
                "ledger_transaction_id": str(ledger_transaction_id),
                "amount_minor": amount_minor,
                "currency": normalized_currency,
                "occurred_at": _serialize_datetime(event_time),
            },
        )

    @staticmethod
    def p2p_transfer_completed(
        *,
        transfer_id: UUID,
        operation_id: UUID,
        sender_user_id: UUID,
        sender_wallet_id: UUID,
        recipient_wallet_id: UUID,
        ledger_transaction_id: UUID,
        amount_minor: int,
        currency: str,
        occurred_at: datetime | None = None,
    ) -> OutboxEvent:
        """Создает событие p2p_transfer.completed.

        Args:
            transfer_id: Идентификатор завершенного P2P-перевода.
            operation_id: Идентификатор бизнес-операции перевода.
            sender_user_id: Идентификатор пользователя-отправителя.
            sender_wallet_id: Идентификатор кошелька отправителя.
            recipient_wallet_id: Идентификатор кошелька получателя.
            ledger_transaction_id: Идентификатор ledger transaction.
            amount_minor: Сумма перевода в минорных единицах.
            currency: Валюта перевода.
            occurred_at: Момент возникновения события.

        Returns:
            Outbox event с JSON-safe payload.

        Raises:
            InvalidOutboxEventError: Если currency пустая после нормализации.
        """
        event_time = _resolve_occurred_at(occurred_at)
        normalized_currency = _normalize_currency(currency)
        return OutboxEvent(
            event_type="p2p_transfer.completed",
            aggregate_type="p2p_transfer",
            aggregate_id=transfer_id,
            occurred_at=event_time,
            payload={
                "transfer_id": str(transfer_id),
                "operation_id": str(operation_id),
                "sender_user_id": str(sender_user_id),
                "sender_wallet_id": str(sender_wallet_id),
                "recipient_wallet_id": str(recipient_wallet_id),
                "ledger_transaction_id": str(ledger_transaction_id),
                "amount_minor": amount_minor,
                "currency": normalized_currency,
                "occurred_at": _serialize_datetime(event_time),
            },
        )


def _resolve_occurred_at(occurred_at: datetime | None) -> datetime:
    return occurred_at if occurred_at is not None else datetime.now(UTC)


def _serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def _normalize_currency(currency: str) -> str:
    normalized_currency = currency.strip().upper()
    if not normalized_currency:
        raise InvalidOutboxEventError("Outbox event currency cannot be empty.")
    return normalized_currency
