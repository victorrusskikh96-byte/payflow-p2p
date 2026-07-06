"""Мапперы между доменными outbox events и SQLAlchemy-моделями."""

from typing import cast

from payflow.modules.outbox.domain import JsonPayload, OutboxEvent, OutboxEventStatus
from payflow.modules.outbox.infrastructure.models import OutboxEventModel


def outbox_event_entity_to_model(event: OutboxEvent) -> OutboxEventModel:
    """Преобразует доменный outbox event в ORM-модель.

    Args:
        event: Доменная сущность outbox event.

    Returns:
        SQLAlchemy-модель outbox event.
    """
    return OutboxEventModel(
        id=event.id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        payload=event.payload,
        status=event.status.value,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
        published_at=event.published_at,
        attempts=event.attempts,
        last_error=event.last_error,
    )


def outbox_event_model_to_entity(event_model: OutboxEventModel) -> OutboxEvent:
    """Преобразует ORM-модель outbox event в доменную сущность.

    Args:
        event_model: SQLAlchemy-модель outbox event.

    Returns:
        Доменная сущность outbox event.
    """
    return OutboxEvent(
        id=event_model.id,
        event_type=event_model.event_type,
        aggregate_type=event_model.aggregate_type,
        aggregate_id=event_model.aggregate_id,
        payload=cast(JsonPayload, event_model.payload),
        status=OutboxEventStatus(event_model.status),
        occurred_at=event_model.occurred_at,
        created_at=event_model.created_at,
        published_at=event_model.published_at,
        attempts=event_model.attempts,
        last_error=event_model.last_error,
    )
