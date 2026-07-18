"""HTTP API P2P-переводов внутри Financial Core."""

from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.core.database import get_async_session
from payflow.modules.auth.api.dependencies import get_current_user
from payflow.modules.financial_core.application.events import OutboxEventWriter
from payflow.modules.financial_core.application.ledger.repositories import (
    LedgerTransactionRepository,
)
from payflow.modules.financial_core.application.transfers import (
    CreateP2PTransferUseCase,
    GetMyTransfersUseCase,
    GetTransferByIdUseCase,
    TransactionManager,
    TransferRepository,
)
from payflow.modules.financial_core.application.transfers.exceptions import (
    InactiveTransferWalletError,
    InsufficientTransferFundsError,
    RecipientWalletNotFoundError,
    SenderWalletNotFoundError,
    TransfersApplicationError,
    TransferWalletCurrencyMismatchError,
    TransferWalletOwnershipError,
)
from payflow.modules.financial_core.application.wallets import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.financial_core.domain.transfers import (
    DuplicateTransferOperationError,
    InvalidTransferAmountError,
    InvalidTransferCurrencyError,
    SameTransferWalletsError,
    Transfer,
    TransferNotFoundError,
    TransferStatus,
)
from payflow.modules.financial_core.domain.wallets import WalletBalanceNotFoundError
from payflow.modules.financial_core.infrastructure.repositories.ledger import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.outbox import (
    SQLAlchemyOutboxEventRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.transfers import (
    SQLAlchemyTransferRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.wallets import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.financial_core.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.domain import User

CurrencyField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=16),
]

router = APIRouter()


class CreateTransferRequest(BaseModel):
    """Описывает запрос на создание P2P-перевода."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation_id": "33333333-3333-4333-8333-333333333333",
                "sender_wallet_id": "22222222-2222-4222-8222-222222222222",
                "recipient_wallet_id": "44444444-4444-4444-8444-444444444444",
                "amount_minor": 2500,
                "currency": "USD",
            }
        }
    )

    operation_id: UUID
    sender_wallet_id: UUID
    recipient_wallet_id: UUID
    amount_minor: int
    currency: CurrencyField


class TransferResponse(BaseModel):
    """Описывает HTTP-представление P2P-перевода."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "55555555-5555-4555-8555-555555555555",
                "operation_id": "33333333-3333-4333-8333-333333333333",
                "sender_user_id": "11111111-1111-4111-8111-111111111111",
                "sender_wallet_id": "22222222-2222-4222-8222-222222222222",
                "recipient_wallet_id": "44444444-4444-4444-8444-444444444444",
                "amount_minor": 2500,
                "currency": "USD",
                "status": "COMPLETED",
                "ledger_transaction_id": "66666666-6666-4666-8666-666666666666",
                "created_at": "2026-07-18T10:15:30+00:00",
                "updated_at": "2026-07-18T10:15:30+00:00",
            }
        }
    )

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

    model_config = ConfigDict(json_schema_extra={"example": {"transfers": []}})

    transfers: list[TransferResponse]


def get_transfer_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TransferRepository:
    """Создает репозиторий P2P-переводов для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий P2P-переводов.
    """
    return SQLAlchemyTransferRepository(session)


def get_wallet_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WalletRepository:
    """Создает репозиторий кошельков для transfer use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий кошельков.
    """
    return SQLAlchemyWalletRepository(session)


def get_wallet_balance_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WalletBalanceRepository:
    """Создает репозиторий проекций балансов для transfer use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий проекций балансов.
    """
    return SQLAlchemyWalletBalanceRepository(session)


def get_ledger_transaction_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> LedgerTransactionRepository:
    """Создает репозиторий ledger transactions для transfer use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий ledger transactions.
    """
    return SQLAlchemyLedgerTransactionRepository(session)


def get_outbox_event_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OutboxEventWriter:
    """Создает репозиторий outbox events для transfer use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий outbox events.
    """
    return SQLAlchemyOutboxEventRepository(session)


def get_transaction_manager(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TransactionManager:
    """Создает менеджер транзакций для transfer use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Менеджер транзакций SQLAlchemy.
    """
    return SQLAlchemyTransactionManager(session)


def get_create_p2p_transfer_use_case(
    transfers: Annotated[
        TransferRepository,
        Depends(get_transfer_repository),
    ],
    wallets: Annotated[WalletRepository, Depends(get_wallet_repository)],
    balances: Annotated[
        WalletBalanceRepository,
        Depends(get_wallet_balance_repository),
    ],
    ledger_transactions: Annotated[
        LedgerTransactionRepository,
        Depends(get_ledger_transaction_repository),
    ],
    outbox_events: Annotated[
        OutboxEventWriter,
        Depends(get_outbox_event_repository),
    ],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
) -> CreateP2PTransferUseCase:
    """Собирает use case создания P2P-перевода.

    Args:
        transfers: Репозиторий P2P-переводов.
        wallets: Репозиторий кошельков.
        balances: Репозиторий проекций балансов.
        ledger_transactions: Репозиторий ledger transactions.
        outbox_events: Репозиторий outbox events.
        transaction_manager: Менеджер транзакций.

    Returns:
        Use case создания P2P-перевода.
    """
    return CreateP2PTransferUseCase(
        transfers=transfers,
        wallets=wallets,
        balances=balances,
        ledger_transactions=ledger_transactions,
        outbox_events=outbox_events,
        transaction_manager=transaction_manager,
    )


def get_my_transfers_use_case(
    transfers: Annotated[
        TransferRepository,
        Depends(get_transfer_repository),
    ],
) -> GetMyTransfersUseCase:
    """Собирает use case получения переводов текущего пользователя.

    Args:
        transfers: Репозиторий P2P-переводов.

    Returns:
        Use case получения списка P2P-переводов.
    """
    return GetMyTransfersUseCase(transfers=transfers)


def get_transfer_by_id_use_case(
    transfers: Annotated[
        TransferRepository,
        Depends(get_transfer_repository),
    ],
) -> GetTransferByIdUseCase:
    """Собирает use case получения P2P-перевода по id.

    Args:
        transfers: Репозиторий P2P-переводов.

    Returns:
        Use case получения P2P-перевода по id.
    """
    return GetTransferByIdUseCase(transfers=transfers)


def _transfer_to_response(transfer: Transfer) -> TransferResponse:
    return TransferResponse(
        id=transfer.id,
        operation_id=transfer.operation_id,
        sender_user_id=transfer.sender_user_id,
        sender_wallet_id=transfer.sender_wallet_id,
        recipient_wallet_id=transfer.recipient_wallet_id,
        amount_minor=transfer.amount_minor,
        currency=transfer.currency,
        status=transfer.status,
        ledger_transaction_id=transfer.ledger_transaction_id,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
    )


def _raise_transfer_not_found(exc: Exception) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Transfer was not found.",
    ) from exc


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать P2P-перевод",
    description=(
        "Выполняет P2P-перевод от кошелька текущего пользователя к кошельку "
        "получателя и возвращает стабильное представление transfer."
    ),
    operation_id="create_transfer",
)
async def create_transfer(
    request: CreateTransferRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    create_p2p_transfer_use_case: Annotated[
        CreateP2PTransferUseCase,
        Depends(get_create_p2p_transfer_use_case),
    ],
) -> TransferResponse:
    """Создает P2P-перевод от текущего пользователя.

    Args:
        request: Данные P2P-перевода.
        current_user: Пользователь, полученный из JWT access token.
        create_p2p_transfer_use_case: Use case создания P2P-перевода.

    Returns:
        Созданный и завершенный P2P-перевод.

    Raises:
        HTTPException: Если запрос некорректен, кошелек недоступен, средств
            недостаточно или operation_id уже использован.
    """
    try:
        result = await create_p2p_transfer_use_case.execute(
            operation_id=request.operation_id,
            sender_user_id=current_user.id,
            sender_wallet_id=request.sender_wallet_id,
            recipient_wallet_id=request.recipient_wallet_id,
            amount_minor=request.amount_minor,
            currency=request.currency,
        )
    except (
        InvalidTransferAmountError,
        InvalidTransferCurrencyError,
        SameTransferWalletsError,
        InactiveTransferWalletError,
        TransferWalletCurrencyMismatchError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transfer request.",
        ) from exc
    except DuplicateTransferOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer operation already exists.",
        ) from exc
    except InsufficientTransferFundsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient transfer funds.",
        ) from exc
    except (
        SenderWalletNotFoundError,
        RecipientWalletNotFoundError,
        TransferWalletOwnershipError,
        WalletBalanceNotFoundError,
    ) as exc:
        _raise_transfer_not_found(exc)
    except TransfersApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transfer operation failed.",
        ) from exc

    return _transfer_to_response(result.transfer)


@router.get(
    "/me",
    response_model=TransferListResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить мои P2P-переводы",
    description="Возвращает исходящие P2P-переводы текущего пользователя.",
    operation_id="get_my_transfers",
)
async def get_my_transfers(
    current_user: Annotated[User, Depends(get_current_user)],
    get_my_transfers_use_case: Annotated[
        GetMyTransfersUseCase,
        Depends(get_my_transfers_use_case),
    ],
) -> TransferListResponse:
    """Возвращает P2P-переводы текущего пользователя.

    Args:
        current_user: Пользователь, полученный из JWT access token.
        get_my_transfers_use_case: Use case получения списка P2P-переводов.

    Returns:
        Список P2P-переводов текущего пользователя.
    """
    transfers = await get_my_transfers_use_case.execute(
        sender_user_id=current_user.id,
    )
    return TransferListResponse(
        transfers=[_transfer_to_response(transfer) for transfer in transfers],
    )


@router.get(
    "/{transfer_id}",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить мой P2P-перевод по id",
    description=(
        "Возвращает исходящий P2P-перевод текущего пользователя. Чужие и "
        "отсутствующие переводы отвечают одинаковым безопасным 404."
    ),
    operation_id="get_transfer_by_id",
)
async def get_transfer_by_id(
    transfer_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    get_transfer_by_id_use_case: Annotated[
        GetTransferByIdUseCase,
        Depends(get_transfer_by_id_use_case),
    ],
) -> TransferResponse:
    """Возвращает P2P-перевод текущего пользователя по id.

    Args:
        transfer_id: Идентификатор P2P-перевода.
        current_user: Пользователь, полученный из JWT access token.
        get_transfer_by_id_use_case: Use case получения P2P-перевода.

    Returns:
        P2P-перевод текущего пользователя.

    Raises:
        HTTPException: Если перевод не найден или принадлежит другому пользователю.
    """
    try:
        transfer = await get_transfer_by_id_use_case.execute(
            sender_user_id=current_user.id,
            transfer_id=transfer_id,
        )
    except TransferNotFoundError as exc:
        _raise_transfer_not_found(exc)

    return _transfer_to_response(transfer)
