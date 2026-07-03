"""Pydantic-схемы HTTP API модуля кошельков."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from payflow.modules.wallets.domain import WalletStatus

CurrencyField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16),
]


class CreateWalletRequest(BaseModel):
    """Описывает запрос на создание кошелька."""

    currency: CurrencyField


class WalletResponse(BaseModel):
    """Описывает HTTP-представление кошелька."""

    id: UUID
    user_id: UUID
    currency: str
    status: WalletStatus
    created_at: datetime
    updated_at: datetime


class WalletBalanceResponse(BaseModel):
    """Описывает HTTP-представление проекции баланса кошелька."""

    wallet_id: UUID
    available_amount_minor: int
    locked_amount_minor: int
    currency: str
    updated_at: datetime


class WalletWithBalanceResponse(BaseModel):
    """Описывает HTTP-представление кошелька с проекцией баланса."""

    wallet: WalletResponse
    balance: WalletBalanceResponse
