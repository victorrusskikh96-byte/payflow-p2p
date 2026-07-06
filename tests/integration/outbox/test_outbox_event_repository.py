"""Интеграционные тесты SQLAlchemy-репозитория outbox events."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payflow.modules.financial_core.domain.outbox import (
    JsonPayload,
    OutboxEvent,
    OutboxEventStatus,
)
from payflow.modules.financial_core.infrastructure.models import OutboxEventModel
from payflow.modules.financial_core.infrastructure.repositories.outbox import (
    SQLAlchemyOutboxEventRepository,
)


def make_outbox_event(
    *,
    event_id: UUID | None = None,
    status: OutboxEventStatus = OutboxEventStatus.PENDING,
    occurred_at: datetime | None = None,
    created_at: datetime | None = None,
    payload: JsonPayload | None = None,
) -> OutboxEvent:
    """Создает outbox event для интеграционных тестов.

    Args:
        event_id: Идентификатор события.
        status: Статус события.
        occurred_at: Момент возникновения события.
        created_at: Момент создания записи.
        payload: Payload события.

    Returns:
        Outbox event с заданными параметрами.
    """
    return OutboxEvent(
        id=event_id,
        event_type="wallet.created",
        aggregate_type="wallet",
        aggregate_id=str(uuid4()),
        payload=payload
        if payload is not None
        else {"wallet_id": str(uuid4()), "currency": "USD"},
        status=status,
        occurred_at=occurred_at,
        created_at=created_at,
        last_error="error" if status is OutboxEventStatus.FAILED else None,
    )


async def test_create_outbox_event(async_session: AsyncSession) -> None:
    """Проверяет создание outbox event в PostgreSQL.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    event = make_outbox_event()

    created_event = await repository.create(event)

    stored_event = await async_session.get(OutboxEventModel, created_event.id)
    assert stored_event is not None
    assert stored_event.event_type == "wallet.created"
    assert stored_event.status == OutboxEventStatus.PENDING.value


async def test_get_outbox_event_by_id(async_session: AsyncSession) -> None:
    """Проверяет поиск outbox event по id.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    created_event = await repository.create(make_outbox_event())

    found_event = await repository.get_by_id(created_event.id)

    assert found_event == created_event


async def test_get_pending_events(async_session: AsyncSession) -> None:
    """Проверяет поиск pending events.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    pending_event = await repository.create(make_outbox_event())
    await repository.create(make_outbox_event(status=OutboxEventStatus.FAILED))

    pending_events = await repository.get_pending(limit=10)

    assert [event.id for event in pending_events] == [pending_event.id]


async def test_pending_events_are_returned_in_oldest_order(
    async_session: AsyncSession,
) -> None:
    """Проверяет сортировку pending events от старых к новым.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    base_time = datetime(2026, 7, 6, 8, 0, tzinfo=UTC)
    repository = SQLAlchemyOutboxEventRepository(async_session)
    newest_event = await repository.create(
        make_outbox_event(occurred_at=base_time + timedelta(minutes=2))
    )
    oldest_event = await repository.create(make_outbox_event(occurred_at=base_time))
    middle_event = await repository.create(
        make_outbox_event(occurred_at=base_time + timedelta(minutes=1))
    )

    pending_events = await repository.get_pending(limit=10)

    assert [event.id for event in pending_events] == [
        oldest_event.id,
        middle_event.id,
        newest_event.id,
    ]


async def test_published_event_is_not_returned_as_pending(
    async_session: AsyncSession,
) -> None:
    """Проверяет, что published event не возвращается как pending.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    event = await repository.create(make_outbox_event())

    published_event = await repository.mark_published(event.id)

    pending_events = await repository.get_pending(limit=10)
    assert published_event is not None
    assert published_event.status is OutboxEventStatus.PUBLISHED
    assert pending_events == []


async def test_failed_event_can_be_found_among_failed(
    async_session: AsyncSession,
) -> None:
    """Проверяет поиск failed event среди failed events.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    event = await repository.create(make_outbox_event())

    failed_event = await repository.mark_failed(event.id, last_error="publish failed")
    failed_events = await repository.get_failed(limit=10)

    assert failed_event is not None
    assert failed_event.status is OutboxEventStatus.FAILED
    assert [event.id for event in failed_events] == [event.id]


async def test_attempts_are_increased(async_session: AsyncSession) -> None:
    """Проверяет увеличение attempts.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    event = await repository.create(make_outbox_event())

    updated_event = await repository.increase_attempts(event.id)

    assert updated_event is not None
    assert updated_event.attempts == 1


async def test_payload_is_saved_and_loaded_correctly(
    async_session: AsyncSession,
) -> None:
    """Проверяет корректное сохранение и чтение payload.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    payload: JsonPayload = {
        "wallet_id": str(uuid4()),
        "created_at": datetime(2026, 7, 6, 9, 0, tzinfo=UTC).isoformat(),
        "amount_minor": 1250,
        "currency": "USD",
    }
    created_event = await repository.create(make_outbox_event(payload=payload))

    found_event = await repository.get_by_id(created_event.id)

    assert found_event is not None
    assert found_event.payload == payload


async def test_failed_event_can_be_returned_to_pending(
    async_session: AsyncSession,
) -> None:
    """Проверяет возврат failed event в pending.

    Args:
        async_session: Асинхронная SQLAlchemy-сессия.
    """
    repository = SQLAlchemyOutboxEventRepository(async_session)
    failed_event = await repository.create(
        make_outbox_event(status=OutboxEventStatus.FAILED)
    )

    pending_event = await repository.return_failed_to_pending(failed_event.id)

    assert pending_event is not None
    assert pending_event.status is OutboxEventStatus.PENDING
    assert pending_event.last_error is None


async def test_repository_uses_existing_transaction(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет, что repository не коммитит существующую транзакцию.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    event_id = uuid4()
    session = async_session_factory()
    try:
        await session.begin()
        repository = SQLAlchemyOutboxEventRepository(session)
        await repository.create(make_outbox_event(event_id=event_id))
        assert await repository.get_by_id(event_id) is not None
        await session.rollback()
    finally:
        await session.close()

    async with async_session_factory() as check_session:
        check_repository = SQLAlchemyOutboxEventRepository(check_session)
        assert await check_repository.get_by_id(event_id) is None


async def test_pending_events_skip_locked_rows(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Проверяет, что pending выборка пропускает заблокированные строки.

    Args:
        async_session_factory: Фабрика асинхронных SQLAlchemy-сессий.
    """
    async with async_session_factory() as setup_session:
        setup_repository = SQLAlchemyOutboxEventRepository(setup_session)
        first_event = await setup_repository.create(make_outbox_event())
        second_event = await setup_repository.create(make_outbox_event())
        await setup_session.commit()

    locker_session = async_session_factory()
    contender_session = async_session_factory()
    try:
        await locker_session.begin()
        locker_repository = SQLAlchemyOutboxEventRepository(locker_session)
        locked_events = await locker_repository.get_pending(limit=1)

        await contender_session.begin()
        contender_repository = SQLAlchemyOutboxEventRepository(contender_session)
        available_events = await contender_repository.get_pending(limit=10)

        assert [event.id for event in locked_events] == [first_event.id]
        assert [event.id for event in available_events] == [second_event.id]
    finally:
        await contender_session.rollback()
        await locker_session.rollback()
        await contender_session.close()
        await locker_session.close()
