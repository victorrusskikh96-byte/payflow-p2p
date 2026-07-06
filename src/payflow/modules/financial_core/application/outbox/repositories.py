"""Интерфейсы репозиториев для application layer модуля outbox."""

from typing import Protocol
from uuid import UUID

from payflow.modules.financial_core.domain.outbox import OutboxEvent


class OutboxEventRepository(Protocol):
    """Определяет контракт хранилища outbox events для application layer."""

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Сохраняет новый outbox event.

        Args:
            event: Доменная сущность outbox event.

        Returns:
            Сохраненный outbox event.
        """

    async def get_by_id(self, event_id: UUID) -> OutboxEvent | None:
        """Возвращает outbox event по идентификатору.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Outbox event или None, если запись не найдена.
        """

    async def get_pending(self, *, limit: int) -> list[OutboxEvent]:
        """Возвращает pending events для будущей публикации.

        Args:
            limit: Максимальное количество событий.

        Returns:
            Список pending events, отсортированных от старых к новым.
        """

    async def get_failed(self, *, limit: int) -> list[OutboxEvent]:
        """Возвращает failed events для анализа или retry.

        Args:
            limit: Максимальное количество событий.

        Returns:
            Список failed events, отсортированных от старых к новым.
        """

    async def mark_published(self, event_id: UUID) -> OutboxEvent | None:
        """Помечает outbox event как опубликованный.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.

        Raises:
            OutboxEventAlreadyPublishedError: Если событие уже опубликовано.
        """

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

    async def increase_attempts(self, event_id: UUID) -> OutboxEvent | None:
        """Увеличивает счетчик попыток публикации.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.
        """

    async def return_failed_to_pending(self, event_id: UUID) -> OutboxEvent | None:
        """Возвращает failed outbox event в pending для повторной обработки.

        Args:
            event_id: Идентификатор outbox event.

        Returns:
            Обновленный outbox event или None, если запись не найдена.
        """
