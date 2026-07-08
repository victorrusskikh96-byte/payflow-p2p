"""Простые application-level события для записи в outbox_events."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonPayload = dict[str, JsonValue]


class OutboxEventStatus(StrEnum):
    """Описывает технический статус строки в таблице outbox_events."""

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class OutboxEventData:
    """Описывает команду записи события в таблицу outbox_events."""

    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: JsonPayload
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Проверяет, что событие можно безопасно сохранить в JSONB.

        Raises:
            ValueError: Если обязательные строки пустые или payload не JSON-safe.
        """
        _ensure_not_empty(self.event_type, field_name="event_type")
        _ensure_not_empty(self.aggregate_type, field_name="aggregate_type")
        _ensure_not_empty(self.aggregate_id, field_name="aggregate_id")
        _normalize_payload(self.payload)


@dataclass(frozen=True, slots=True)
class OutboxEventRecord:
    """Описывает строку outbox_events, прочитанную из базы данных."""

    id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: JsonPayload
    status: OutboxEventStatus
    occurred_at: datetime
    created_at: datetime
    published_at: datetime | None
    attempts: int
    last_error: str | None


class OutboxEventWriter(Protocol):
    """Определяет минимальный порт записи outbox events для use cases."""

    async def create(self, event: OutboxEventData) -> OutboxEventRecord:
        """Сохраняет outbox event в текущей database transaction.

        Args:
            event: Данные события для записи в outbox_events.

        Returns:
            Сохраненная строка outbox_events.
        """


def wallet_created_event(
    *,
    wallet_id: UUID,
    user_id: UUID,
    currency: str,
    occurred_at: datetime | None = None,
) -> OutboxEventData:
    """Создает данные события wallet.created.

    Args:
        wallet_id: Идентификатор созданного кошелька.
        user_id: Идентификатор владельца кошелька.
        currency: Валюта кошелька.
        occurred_at: Момент возникновения события.

    Returns:
        Данные события с JSON-safe payload.

    Raises:
        ValueError: Если currency пустая после нормализации.
    """
    event_time = _resolve_occurred_at(occurred_at)
    normalized_currency = _normalize_currency(currency)
    return OutboxEventData(
        event_type="wallet.created",
        aggregate_type="wallet",
        aggregate_id=str(wallet_id),
        occurred_at=event_time,
        payload={
            "wallet_id": str(wallet_id),
            "user_id": str(user_id),
            "currency": normalized_currency,
            "occurred_at": _serialize_datetime(event_time),
        },
    )


def internal_deposit_completed_event(
    *,
    operation_id: UUID,
    source_wallet_id: UUID,
    target_wallet_id: UUID,
    ledger_transaction_id: UUID,
    amount_minor: int,
    currency: str,
    occurred_at: datetime | None = None,
) -> OutboxEventData:
    """Создает данные события internal_deposit.completed.

    Args:
        operation_id: Идентификатор операции internal deposit.
        source_wallet_id: Идентификатор funding wallet.
        target_wallet_id: Идентификатор пополняемого кошелька.
        ledger_transaction_id: Идентификатор ledger transaction.
        amount_minor: Сумма операции в минорных единицах.
        currency: Валюта операции.
        occurred_at: Момент возникновения события.

    Returns:
        Данные события с JSON-safe payload.

    Raises:
        ValueError: Если currency пустая после нормализации.
    """
    event_time = _resolve_occurred_at(occurred_at)
    normalized_currency = _normalize_currency(currency)
    return OutboxEventData(
        event_type="internal_deposit.completed",
        aggregate_type="internal_deposit",
        aggregate_id=str(operation_id),
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


def p2p_transfer_completed_event(
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
) -> OutboxEventData:
    """Создает данные события p2p_transfer.completed.

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
        Данные события с JSON-safe payload.

    Raises:
        ValueError: Если currency пустая после нормализации.
    """
    event_time = _resolve_occurred_at(occurred_at)
    normalized_currency = _normalize_currency(currency)
    return OutboxEventData(
        event_type="p2p_transfer.completed",
        aggregate_type="p2p_transfer",
        aggregate_id=str(transfer_id),
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
        raise ValueError("Outbox event currency cannot be empty.")
    return normalized_currency


def _ensure_not_empty(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"Outbox event {field_name} cannot be empty.")


def _normalize_payload(payload: Mapping[str, JsonValue]) -> JsonPayload:
    if not isinstance(payload, Mapping):
        raise ValueError("Outbox event payload must be dict-like.")

    normalized_payload = dict(payload)
    if any(not isinstance(key, str) for key in normalized_payload):
        raise ValueError("Outbox event payload keys must be strings.")

    try:
        json.dumps(normalized_payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Outbox event payload must be JSON-serializable.") from exc

    return normalized_payload
