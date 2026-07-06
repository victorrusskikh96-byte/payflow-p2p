"""Unit-тесты фабрики outbox events."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from payflow.modules.outbox.application.event_factory import OutboxEventFactory


def test_wallet_created_has_correct_event_type() -> None:
    """Проверяет event_type события wallet.created."""
    event = OutboxEventFactory.wallet_created(
        wallet_id=uuid4(),
        user_id=uuid4(),
        currency="USD",
    )

    assert event.event_type == "wallet.created"


def test_internal_deposit_completed_has_correct_event_type() -> None:
    """Проверяет event_type события internal_deposit.completed."""
    event = OutboxEventFactory.internal_deposit_completed(
        operation_id=uuid4(),
        source_wallet_id=uuid4(),
        target_wallet_id=uuid4(),
        ledger_transaction_id=uuid4(),
        amount_minor=100,
        currency="USD",
    )

    assert event.event_type == "internal_deposit.completed"


def test_p2p_transfer_completed_has_correct_event_type() -> None:
    """Проверяет event_type события p2p_transfer.completed."""
    event = OutboxEventFactory.p2p_transfer_completed(
        transfer_id=uuid4(),
        operation_id=uuid4(),
        sender_user_id=uuid4(),
        sender_wallet_id=uuid4(),
        recipient_wallet_id=uuid4(),
        ledger_transaction_id=uuid4(),
        amount_minor=100,
        currency="USD",
    )

    assert event.event_type == "p2p_transfer.completed"


def test_uuid_and_datetime_are_serialized_as_json_safe_values() -> None:
    """Проверяет сериализацию UUID и datetime в JSON-safe формат."""
    wallet_id = uuid4()
    user_id = uuid4()
    occurred_at = datetime(2026, 7, 6, 9, 30, tzinfo=UTC)

    event = OutboxEventFactory.wallet_created(
        wallet_id=wallet_id,
        user_id=user_id,
        currency="usd",
        occurred_at=occurred_at,
    )

    assert event.payload["wallet_id"] == str(wallet_id)
    assert event.payload["user_id"] == str(user_id)
    assert event.payload["occurred_at"] == occurred_at.isoformat()
    assert isinstance(event.payload["wallet_id"], str)
    assert isinstance(event.payload["occurred_at"], str)


def test_internal_deposit_payload_contains_amount_and_currency() -> None:
    """Проверяет amount_minor и currency в payload internal deposit."""
    event = OutboxEventFactory.internal_deposit_completed(
        operation_id=uuid4(),
        source_wallet_id=uuid4(),
        target_wallet_id=uuid4(),
        ledger_transaction_id=uuid4(),
        amount_minor=250,
        currency="usd",
    )

    assert event.payload["amount_minor"] == 250
    assert event.payload["currency"] == "USD"


def test_p2p_transfer_payload_contains_amount_and_currency() -> None:
    """Проверяет amount_minor и currency в payload P2P-перевода."""
    event = OutboxEventFactory.p2p_transfer_completed(
        transfer_id=uuid4(),
        operation_id=uuid4(),
        sender_user_id=uuid4(),
        sender_wallet_id=uuid4(),
        recipient_wallet_id=uuid4(),
        ledger_transaction_id=uuid4(),
        amount_minor=300,
        currency="eur",
    )

    assert event.payload["amount_minor"] == 300
    assert event.payload["currency"] == "EUR"


def test_payload_uuid_fields_are_strings() -> None:
    """Проверяет, что UUID-поля в payload представлены строками."""
    transfer_id = uuid4()
    event = OutboxEventFactory.p2p_transfer_completed(
        transfer_id=transfer_id,
        operation_id=uuid4(),
        sender_user_id=uuid4(),
        sender_wallet_id=uuid4(),
        recipient_wallet_id=uuid4(),
        ledger_transaction_id=uuid4(),
        amount_minor=100,
        currency="USD",
    )

    assert event.payload["transfer_id"] == str(transfer_id)
    assert isinstance(event.payload["transfer_id"], str)
    UUID(event.payload["transfer_id"])
