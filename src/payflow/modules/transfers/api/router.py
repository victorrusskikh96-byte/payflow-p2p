"""HTTP-маршруты модуля P2P-переводов."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from payflow.modules.auth.api.dependencies import get_current_user
from payflow.modules.transfers.api.dependencies import (
    get_create_p2p_transfer_use_case,
    get_my_transfers_use_case,
    get_transfer_by_id_use_case,
)
from payflow.modules.transfers.api.schemas import (
    CreateTransferRequest,
    TransferListResponse,
    TransferResponse,
)
from payflow.modules.transfers.application import (
    CreateP2PTransferUseCase,
    GetMyTransfersUseCase,
    GetTransferByIdUseCase,
)
from payflow.modules.transfers.application.exceptions import (
    InactiveTransferWalletError,
    InsufficientTransferFundsError,
    RecipientWalletNotFoundError,
    SenderWalletNotFoundError,
    TransferWalletCurrencyMismatchError,
    TransferWalletOwnershipError,
)
from payflow.modules.transfers.domain import (
    DuplicateTransferOperationError,
    InvalidTransferAmountError,
    InvalidTransferCurrencyError,
    SameTransferWalletsError,
    Transfer,
    TransferNotFoundError,
)
from payflow.modules.users.domain import User
from payflow.modules.wallets.domain import WalletBalanceNotFoundError

router = APIRouter()


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

    return _transfer_to_response(result.transfer)


@router.get(
    "/me",
    response_model=TransferListResponse,
    status_code=status.HTTP_200_OK,
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
