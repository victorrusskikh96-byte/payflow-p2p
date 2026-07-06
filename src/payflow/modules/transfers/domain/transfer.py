"""Доменная модель пользовательского P2P-перевода."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from payflow.modules.transfers.domain.exceptions import (
    InvalidTransferAmountError,
    InvalidTransferCurrencyError,
    InvalidTransferStatusError,
    SameTransferWalletsError,
)


class TransferStatus(StrEnum):
    """Описывает состояние пользовательского P2P-перевода."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True, init=False)
class Transfer:
    """Представляет пользовательский P2P-перевод между двумя кошельками."""

    id: UUID
    operation_id: UUID
    sender_user_id: UUID
    sender_wallet_id: UUID
    recipient_wallet_id: UUID
    amount_minor: int
    currency: str
    status: TransferStatus
    ledger_transaction_id: UUID | None
    created_at: datetime
    updated_at: datetime
    failed_at: datetime | None

    def __init__(
        self,
        *,
        operation_id: UUID,
        sender_user_id: UUID,
        sender_wallet_id: UUID,
        recipient_wallet_id: UUID,
        amount_minor: int,
        currency: str,
        id: UUID | None = None,
        status: TransferStatus = TransferStatus.PENDING,
        ledger_transaction_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        failed_at: datetime | None = None,
    ) -> None:
        """Создает P2P-перевод и проверяет доменные инварианты.

        Args:
            operation_id: Идентификатор бизнес-операции перевода.
            sender_user_id: Идентификатор пользователя-отправителя.
            sender_wallet_id: Идентификатор кошелька отправителя.
            recipient_wallet_id: Идентификатор кошелька получателя.
            amount_minor: Сумма перевода в минорных единицах.
            currency: Код валюты перевода.
            id: Идентификатор перевода, если он уже существует.
            status: Текущий статус перевода.
            ledger_transaction_id: Идентификатор ledger transaction, если она создана.
            created_at: Дата создания перевода.
            updated_at: Дата последнего обновления перевода.
            failed_at: Дата неуспешного завершения перевода.

        Raises:
            InvalidTransferAmountError: Если сумма не больше нуля.
            InvalidTransferCurrencyError: Если валюта пустая после нормализации.
            SameTransferWalletsError: Если кошельки отправителя и получателя совпадают.
        """
        self._validate_amount(amount_minor)
        self._validate_wallets(sender_wallet_id, recipient_wallet_id)

        now = datetime.now(UTC)

        self.id = id if id is not None else uuid4()
        self.operation_id = operation_id
        self.sender_user_id = sender_user_id
        self.sender_wallet_id = sender_wallet_id
        self.recipient_wallet_id = recipient_wallet_id
        self.amount_minor = amount_minor
        self.currency = self._normalize_currency(currency)
        self.status = status
        self.ledger_transaction_id = ledger_transaction_id
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.created_at
        self.failed_at = failed_at

    def complete(self, *, ledger_transaction_id: UUID) -> None:
        """Переводит P2P-перевод в статус COMPLETED.

        Args:
            ledger_transaction_id: Идентификатор committed ledger transaction.

        Raises:
            InvalidTransferStatusError: Если перевод уже не находится в PENDING.
        """
        self._ensure_pending()
        self.status = TransferStatus.COMPLETED
        self.ledger_transaction_id = ledger_transaction_id
        self.updated_at = datetime.now(UTC)

    def fail(self) -> None:
        """Переводит P2P-перевод в статус FAILED.

        Raises:
            InvalidTransferStatusError: Если перевод уже не находится в PENDING.
        """
        self._ensure_pending()
        now = datetime.now(UTC)
        self.status = TransferStatus.FAILED
        self.updated_at = now
        self.failed_at = now

    def is_completed(self) -> bool:
        """Проверяет, завершен ли перевод успешно.

        Returns:
            True, если статус перевода равен COMPLETED.
        """
        return self.status is TransferStatus.COMPLETED

    def _ensure_pending(self) -> None:
        if self.status is not TransferStatus.PENDING:
            raise InvalidTransferStatusError("Transfer is not pending.")

    @staticmethod
    def _validate_amount(amount_minor: int) -> None:
        if amount_minor <= 0:
            raise InvalidTransferAmountError("Transfer amount must be positive.")

    @staticmethod
    def _validate_wallets(sender_wallet_id: UUID, recipient_wallet_id: UUID) -> None:
        if sender_wallet_id == recipient_wallet_id:
            raise SameTransferWalletsError(
                "Transfer sender and recipient wallets must differ.",
            )

    @staticmethod
    def _normalize_currency(currency: str) -> str:
        normalized_currency = currency.strip().upper()
        if not normalized_currency:
            raise InvalidTransferCurrencyError("Transfer currency cannot be empty.")
        return normalized_currency
