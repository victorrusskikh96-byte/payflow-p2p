"""SQLAlchemy-репозиторий таблицы outbox_events."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.financial_core.application.events import (
    JsonPayload,
    OutboxEventData,
    OutboxEventRecord,
    OutboxEventStatus,
    OutboxEventWriter,
)
from payflow.modules.financial_core.infrastructure.models import OutboxEventModel


class SQLAlchemyOutboxEventRepository(OutboxEventWriter):
    """Работает с таблицей outbox_events через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий outbox events.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, event: OutboxEventData) -> OutboxEventRecord:
        """Сохраняет новый outbox event в текущей database transaction.

        Args:
            event: Данные события для записи в outbox_events.

        Returns:
            Сохраненная строка outbox_events.

        Raises:
            sqlalchemy.exc.IntegrityError: Если база данных отклоняет ограничения.
        """
        now = datetime.now(UTC)
        event_model = OutboxEventModel(
            id=event.id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            status=OutboxEventStatus.PENDING.value,
            occurred_at=event.occurred_at,
            created_at=now,
            published_at=None,
            attempts=0,
            last_error=None,
        )
        self._session.add(event_model)
        await self._session.flush()
        return _model_to_record(event_model)

    async def get_by_id(self, event_id: UUID) -> OutboxEventRecord | None:
        """Возвращает outbox event по идентификатору.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Outbox event или None, если запись не найдена.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None
        return _model_to_record(event_model)

    async def get_pending(self, *, limit: int) -> list[OutboxEventRecord]:
        """Возвращает pending events с row-level lock и SKIP LOCKED.

        Args:
            limit: Максимальное количество событий.

        Returns:
            Список pending events, отсортированных от старых к новым.
        """
        if limit <= 0:
            return []

        statement = (
            select(OutboxEventModel)
            .where(OutboxEventModel.status == OutboxEventStatus.PENDING.value)
            .order_by(
                OutboxEventModel.occurred_at,
                OutboxEventModel.created_at,
                OutboxEventModel.id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.scalars(statement)
        return [_model_to_record(event_model) for event_model in result.all()]

    async def get_failed(self, *, limit: int) -> list[OutboxEventRecord]:
        """Возвращает failed events для тестов и диагностики.

        Args:
            limit: Максимальное количество событий.

        Returns:
            Список failed events, отсортированных от старых к новым.
        """
        if limit <= 0:
            return []

        statement = (
            select(OutboxEventModel)
            .where(OutboxEventModel.status == OutboxEventStatus.FAILED.value)
            .order_by(
                OutboxEventModel.occurred_at,
                OutboxEventModel.created_at,
                OutboxEventModel.id,
            )
            .limit(limit)
        )
        result = await self._session.scalars(statement)
        return [_model_to_record(event_model) for event_model in result.all()]

    async def mark_published(self, event_id: UUID) -> OutboxEventRecord | None:
        """Помечает outbox event как опубликованный.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.

        Raises:
            ValueError: Если событие уже опубликовано.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None
        if event_model.status == OutboxEventStatus.PUBLISHED.value:
            raise ValueError("Outbox event is already published.")

        event_model.status = OutboxEventStatus.PUBLISHED.value
        event_model.published_at = datetime.now(UTC)
        event_model.last_error = None
        await self._session.flush()
        return _model_to_record(event_model)

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        last_error: str,
    ) -> OutboxEventRecord | None:
        """Помечает outbox event как failed и сохраняет последнюю ошибку.

        Args:
            event_id: Идентификатор outbox event.
            last_error: Текст последней ошибки.

        Returns:
            Обновленный outbox event или None, если запись не найдена.

        Raises:
            ValueError: Если текст ошибки пустой.
        """
        normalized_error = last_error.strip()
        if not normalized_error:
            raise ValueError("Outbox event last_error cannot be empty.")

        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None

        event_model.status = OutboxEventStatus.FAILED.value
        event_model.last_error = normalized_error
        event_model.attempts += 1
        await self._session.flush()
        return _model_to_record(event_model)

    async def increase_attempts(self, event_id: UUID) -> OutboxEventRecord | None:
        """Увеличивает счетчик попыток обработки события.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None

        event_model.attempts += 1
        await self._session.flush()
        return _model_to_record(event_model)

    async def return_failed_to_pending(
        self,
        event_id: UUID,
    ) -> OutboxEventRecord | None:
        """Возвращает failed outbox event в pending для будущей обработки.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None

        if event_model.status == OutboxEventStatus.FAILED.value:
            event_model.status = OutboxEventStatus.PENDING.value
            event_model.last_error = None
        await self._session.flush()
        return _model_to_record(event_model)


def _model_to_record(event_model: OutboxEventModel) -> OutboxEventRecord:
    return OutboxEventRecord(
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
