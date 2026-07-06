"""SQLAlchemy-репозиторий outbox events."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.outbox.application.repositories import OutboxEventRepository
from payflow.modules.outbox.domain import OutboxEvent, OutboxEventStatus
from payflow.modules.outbox.infrastructure.mappers import (
    outbox_event_entity_to_model,
    outbox_event_model_to_entity,
)
from payflow.modules.outbox.infrastructure.models import OutboxEventModel


class SQLAlchemyOutboxEventRepository(OutboxEventRepository):
    """Работает с outbox events через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий outbox events.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Сохраняет новый outbox event в базе данных.

        Args:
            event: Доменная сущность outbox event.

        Returns:
            Сохраненный outbox event.

        Raises:
            sqlalchemy.exc.IntegrityError: Если база данных отклоняет ограничения.
        """
        event_model = outbox_event_entity_to_model(event)
        self._session.add(event_model)
        await self._session.flush()
        return outbox_event_model_to_entity(event_model)

    async def get_by_id(self, event_id: UUID) -> OutboxEvent | None:
        """Возвращает outbox event по идентификатору.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Outbox event или None, если запись не найдена.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None
        return outbox_event_model_to_entity(event_model)

    async def get_pending(self, *, limit: int) -> list[OutboxEvent]:
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
        return [
            outbox_event_model_to_entity(event_model) for event_model in result.all()
        ]

    async def get_failed(self, *, limit: int) -> list[OutboxEvent]:
        """Возвращает failed events.

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
        return [
            outbox_event_model_to_entity(event_model) for event_model in result.all()
        ]

    async def mark_published(self, event_id: UUID) -> OutboxEvent | None:
        """Помечает outbox event как опубликованный.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.

        Raises:
            OutboxEventAlreadyPublishedError: Если событие уже опубликовано.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None

        event = outbox_event_model_to_entity(event_model)
        event.mark_published()
        self._apply_entity(event_model, event)
        await self._session.flush()
        return outbox_event_model_to_entity(event_model)

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        last_error: str,
    ) -> OutboxEvent | None:
        """Помечает outbox event как failed и сохраняет последнюю ошибку.

        Args:
            event_id: Идентификатор outbox event.
            last_error: Текст последней ошибки.

        Returns:
            Обновленный outbox event или None, если запись не найдена.

        Raises:
            InvalidOutboxEventError: Если текст ошибки пустой.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None

        event = outbox_event_model_to_entity(event_model)
        event.mark_failed(last_error=last_error)
        self._apply_entity(event_model, event)
        await self._session.flush()
        return outbox_event_model_to_entity(event_model)

    async def increase_attempts(self, event_id: UUID) -> OutboxEvent | None:
        """Увеличивает счетчик попыток публикации.

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
        return outbox_event_model_to_entity(event_model)

    async def return_failed_to_pending(self, event_id: UUID) -> OutboxEvent | None:
        """Возвращает failed outbox event в pending для повторной обработки.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.
        """
        event_model = await self._session.get(OutboxEventModel, event_id)
        if event_model is None:
            return None

        event = outbox_event_model_to_entity(event_model)
        event.mark_pending()
        self._apply_entity(event_model, event)
        await self._session.flush()
        return outbox_event_model_to_entity(event_model)

    @staticmethod
    def _apply_entity(event_model: OutboxEventModel, event: OutboxEvent) -> None:
        event_model.event_type = event.event_type
        event_model.aggregate_type = event.aggregate_type
        event_model.aggregate_id = event.aggregate_id
        event_model.payload = event.payload
        event_model.status = event.status.value
        event_model.occurred_at = event.occurred_at
        event_model.created_at = event.created_at
        event_model.published_at = event.published_at
        event_model.attempts = event.attempts
        event_model.last_error = event.last_error
