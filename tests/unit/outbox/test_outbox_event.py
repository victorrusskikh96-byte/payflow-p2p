"""Unit-тесты простых данных outbox events."""

from typing import cast
from uuid import uuid4

import pytest

from payflow.modules.financial_core.application.events import (
    JsonPayload,
    OutboxEventData,
)


def _make_outbox_event_data(
    *,
    event_type: str = "wallet.created",
    aggregate_type: str = "wallet",
    aggregate_id: str | None = None,
    payload: JsonPayload | None = None,
) -> OutboxEventData:
    """Создает данные outbox event для unit-тестов.

    Args:
        event_type: Тип события.
        aggregate_type: Тип агрегата.
        aggregate_id: Идентификатор агрегата.
        payload: Payload события.

    Returns:
        Данные события с заданными параметрами.
    """
    return OutboxEventData(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id if aggregate_id is not None else str(uuid4()),
        payload=payload
        if payload is not None
        else {"wallet_id": str(uuid4()), "amount_minor": 100},
    )


def test_event_data_is_created_with_id() -> None:
    """Проверяет создание данных события с идентификатором."""
    event = _make_outbox_event_data()

    assert event.id is not None


@pytest.mark.parametrize("event_type", ["", "   "])
def test_empty_event_type_is_forbidden(event_type: str) -> None:
    """Проверяет запрет пустого типа события.

    Args:
        event_type: Пустой или пробельный тип события из параметров теста.
    """
    with pytest.raises(ValueError):
        _make_outbox_event_data(event_type=event_type)


@pytest.mark.parametrize("aggregate_type", ["", "   "])
def test_empty_aggregate_type_is_forbidden(aggregate_type: str) -> None:
    """Проверяет запрет пустого типа агрегата.

    Args:
        aggregate_type: Пустой или пробельный тип агрегата из параметров теста.
    """
    with pytest.raises(ValueError):
        _make_outbox_event_data(aggregate_type=aggregate_type)


@pytest.mark.parametrize("aggregate_id", ["", "   "])
def test_empty_aggregate_id_is_forbidden(aggregate_id: str) -> None:
    """Проверяет запрет пустого идентификатора агрегата.

    Args:
        aggregate_id: Пустой или пробельный идентификатор из параметров теста.
    """
    with pytest.raises(ValueError):
        _make_outbox_event_data(aggregate_id=aggregate_id)


def test_non_json_safe_payload_is_forbidden() -> None:
    """Проверяет запрет payload, который нельзя сериализовать в JSON."""
    with pytest.raises(ValueError):
        _make_outbox_event_data(payload=cast(JsonPayload, {"wallet_id": uuid4()}))
