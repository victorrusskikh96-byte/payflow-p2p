"""Pydantic-схемы HTTP API модуля P2P-переводов."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from payflow.modules.transfers.domain import TransferStatus

CurrencyField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16),
]


class CreateTransferRequest(BaseModel):
    """Описывает запрос на создание P2P-перевода."""

    operation_id: UUID
    sender_wallet_id: UUID
    recipient_wallet_id: UUID
    amount_minor: int
    currency: CurrencyField


class TransferResponse(BaseModel):
    """Описывает HTTP-представление P2P-перевода."""

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


class TransferListResponse(BaseModel):
    """Описывает HTTP-представление списка P2P-переводов."""

    transfers: list[TransferResponse]
