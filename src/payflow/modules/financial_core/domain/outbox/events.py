"""Доменная модель outbox event и правила смены статусов."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from payflow.modules.financial_core.domain.outbox.exceptions import (
    InvalidOutboxEventError,
    OutboxEventAlreadyPublishedError,
)

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonPayload = dict[str, JsonValue]


class OutboxEventStatus(StrEnum):
    """Описывает состояние outbox event."""

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass(slots=True, init=False)
class OutboxEvent:
    """Представляет событие outbox, сохраненное вместе с бизнес-операцией."""

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

    def __init__(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str | UUID,
        payload: Mapping[str, JsonValue],
        id: UUID | None = None,
        status: OutboxEventStatus = OutboxEventStatus.PENDING,
        occurred_at: datetime | None = None,
        created_at: datetime | None = None,
        published_at: datetime | None = None,
        attempts: int = 0,
        last_error: str | None = None,
    ) -> None:
        """Создает outbox event и проверяет доменные инварианты.

        Args:
            event_type: Тип события для будущего publisher.
            aggregate_type: Тип агрегата, породившего событие.
            aggregate_id: Идентификатор агрегата, породившего событие.
            payload: JSON-serializable payload события.
            id: Идентификатор события, если оно уже существует.
            status: Текущий статус события.
            occurred_at: Момент возникновения события в домене.
            created_at: Момент сохранения события в outbox.
            published_at: Момент публикации события, если оно опубликовано.
            attempts: Количество попыток публикации.
            last_error: Последняя ошибка публикации, если она была.

        Raises:
            InvalidOutboxEventError: Если параметры события нарушают инварианты.
        """
        now = datetime.now(UTC)

        self.id = id if id is not None else uuid4()
        self.event_type = self._normalize_required_string(
            event_type,
            field_name="event_type",
        )
        self.aggregate_type = self._normalize_required_string(
            aggregate_type,
            field_name="aggregate_type",
        )
        self.aggregate_id = self._normalize_required_string(
            str(aggregate_id),
            field_name="aggregate_id",
        )
        self.payload = self._normalize_payload(payload)
        self.status = status
        self.occurred_at = occurred_at if occurred_at is not None else now
        self.created_at = created_at if created_at is not None else now
        self.published_at = published_at
        self.attempts = self._validate_attempts(attempts)
        self.last_error = last_error

    def mark_published(self, *, published_at: datetime | None = None) -> None:
        """Переводит outbox event в статус PUBLISHED.

        Args:
            published_at: Момент публикации события.

        Raises:
            OutboxEventAlreadyPublishedError: Если событие уже опубликовано.
        """
        if self.status is OutboxEventStatus.PUBLISHED:
            raise OutboxEventAlreadyPublishedError("Outbox event is already published.")

        self.status = OutboxEventStatus.PUBLISHED
        self.published_at = (
            published_at if published_at is not None else datetime.now(UTC)
        )
        self.last_error = None

    def mark_failed(self, *, last_error: str) -> None:
        """Переводит outbox event в статус FAILED и сохраняет ошибку.

        Args:
            last_error: Текст последней ошибки публикации.

        Raises:
            InvalidOutboxEventError: Если текст ошибки пустой.
        """
        self.status = OutboxEventStatus.FAILED
        self.last_error = self._normalize_required_string(
            last_error,
            field_name="last_error",
        )
        self.attempts += 1

    def mark_pending(self) -> None:
        """Возвращает failed outbox event в статус PENDING для будущего retry."""
        if self.status is OutboxEventStatus.FAILED:
            self.status = OutboxEventStatus.PENDING
            self.last_error = None

    @staticmethod
    def _normalize_required_string(value: str, *, field_name: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise InvalidOutboxEventError(f"Outbox event {field_name} cannot be empty.")
        return normalized_value

    @staticmethod
    def _normalize_payload(payload: Mapping[str, JsonValue]) -> JsonPayload:
        if not isinstance(payload, Mapping):
            raise InvalidOutboxEventError("Outbox event payload must be dict-like.")

        normalized_payload = dict(payload)
        if any(not isinstance(key, str) for key in normalized_payload):
            raise InvalidOutboxEventError("Outbox event payload keys must be strings.")

        try:
            json.dumps(normalized_payload)
        except (TypeError, ValueError) as exc:
            raise InvalidOutboxEventError(
                "Outbox event payload must be JSON-serializable.",
            ) from exc

        return normalized_payload

    @staticmethod
    def _validate_attempts(attempts: int) -> int:
        if attempts < 0:
            raise InvalidOutboxEventError("Outbox event attempts cannot be negative.")
        return attempts
