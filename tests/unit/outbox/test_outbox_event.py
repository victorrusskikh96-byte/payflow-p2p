"""Unit-тесты доменной модели outbox event."""

from uuid import uuid4

import pytest

from payflow.modules.outbox.domain import (
    InvalidOutboxEventError,
    OutboxEvent,
    OutboxEventAlreadyPublishedError,
    OutboxEventStatus,
)


def _make_outbox_event(
    *,
    event_type: str = "TransferCompleted",
    aggregate_type: str = "Transfer",
    aggregate_id: str | None = None,
) -> OutboxEvent:
    """Создает outbox event для unit-тестов.

    Args:
        event_type: Тип события.
        aggregate_type: Тип агрегата.
        aggregate_id: Идентификатор агрегата.

    Returns:
        Outbox event с заданными параметрами.
    """
    return OutboxEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id if aggregate_id is not None else str(uuid4()),
        payload={"transfer_id": str(uuid4()), "amount_minor": 100},
    )


def test_event_is_created_with_pending_status() -> None:
    """Проверяет создание события в статусе PENDING."""
    event = _make_outbox_event()

    assert event.status is OutboxEventStatus.PENDING


@pytest.mark.parametrize("event_type", ["", "   "])
def test_empty_event_type_is_forbidden(event_type: str) -> None:
    """Проверяет запрет пустого типа события.

    Args:
        event_type: Пустой или пробельный тип события из параметров теста.
    """
    with pytest.raises(InvalidOutboxEventError):
        _make_outbox_event(event_type=event_type)


@pytest.mark.parametrize("aggregate_type", ["", "   "])
def test_empty_aggregate_type_is_forbidden(aggregate_type: str) -> None:
    """Проверяет запрет пустого типа агрегата.

    Args:
        aggregate_type: Пустой или пробельный тип агрегата из параметров теста.
    """
    with pytest.raises(InvalidOutboxEventError):
        _make_outbox_event(aggregate_type=aggregate_type)


@pytest.mark.parametrize("aggregate_id", ["", "   "])
def test_empty_aggregate_id_is_forbidden(aggregate_id: str) -> None:
    """Проверяет запрет пустого идентификатора агрегата.

    Args:
        aggregate_id: Пустой или пробельный идентификатор из параметров теста.
    """
    with pytest.raises(InvalidOutboxEventError):
        _make_outbox_event(aggregate_id=aggregate_id)


def test_attempts_default_to_zero() -> None:
    """Проверяет значение attempts по умолчанию."""
    event = _make_outbox_event()

    assert event.attempts == 0


def test_event_can_be_marked_as_published() -> None:
    """Проверяет перевод события в статус PUBLISHED."""
    event = _make_outbox_event()

    event.mark_published()

    assert event.status is OutboxEventStatus.PUBLISHED
    assert event.published_at is not None


def test_published_event_cannot_be_published_again() -> None:
    """Проверяет запрет повторной публикации события."""
    event = _make_outbox_event()
    event.mark_published()

    with pytest.raises(OutboxEventAlreadyPublishedError):
        event.mark_published()


def test_event_can_be_marked_as_failed_with_last_error() -> None:
    """Проверяет перевод события в статус FAILED с последней ошибкой."""
    event = _make_outbox_event()

    event.mark_failed(last_error="Kafka is unavailable.")

    assert event.status is OutboxEventStatus.FAILED
    assert event.last_error == "Kafka is unavailable."
