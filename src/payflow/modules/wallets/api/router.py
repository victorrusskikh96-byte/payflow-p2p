"""HTTP-маршруты модуля кошельков."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from payflow.modules.auth.api.dependencies import get_current_user
from payflow.modules.users.domain import User
from payflow.modules.wallets.api.dependencies import (
    get_create_wallet_use_case,
    get_my_wallets_use_case,
    get_wallet_by_id_use_case,
)
from payflow.modules.wallets.api.schemas import (
    CreateWalletRequest,
    WalletBalanceResponse,
    WalletResponse,
    WalletWithBalanceResponse,
)
from payflow.modules.wallets.application import (
    CreateWalletUseCase,
    GetMyWalletsUseCase,
    GetWalletByIdUseCase,
    WalletWithBalance,
)
from payflow.modules.wallets.domain import (
    InvalidWalletCurrencyError,
    WalletAlreadyExistsError,
    WalletNotFoundError,
    WalletOwnerUnavailableError,
)

router = APIRouter()


def _wallet_with_balance_to_response(
    wallet_with_balance: WalletWithBalance,
) -> WalletWithBalanceResponse:
    wallet = wallet_with_balance.wallet
    balance = wallet_with_balance.balance
    return WalletWithBalanceResponse(
        wallet=WalletResponse(
            id=wallet.id,
            user_id=wallet.user_id,
            currency=wallet.currency,
            status=wallet.status,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        ),
        balance=WalletBalanceResponse(
            wallet_id=balance.wallet_id,
            available_amount_minor=balance.available_amount_minor,
            locked_amount_minor=balance.locked_amount_minor,
            currency=balance.currency,
            updated_at=balance.updated_at,
        ),
    )


def _raise_wallet_not_found(exc: Exception) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Wallet was not found.",
    ) from exc


@router.post(
    "",
    response_model=WalletWithBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet(
    request: CreateWalletRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    create_wallet_use_case: Annotated[
        CreateWalletUseCase,
        Depends(get_create_wallet_use_case),
    ],
) -> WalletWithBalanceResponse:
    """Создает кошелек текущего пользователя.

    Args:
        request: Данные создания кошелька.
        current_user: Пользователь, полученный из JWT access token.
        create_wallet_use_case: Use case создания кошелька.

    Returns:
        Созданный кошелек с нулевой проекцией баланса.

    Raises:
        HTTPException: Если пользователь недоступен, валюта некорректна или
            кошелек в такой валюте уже существует.
    """
    try:
        wallet_with_balance = await create_wallet_use_case.execute(
            user_id=current_user.id,
            currency=request.currency,
        )
    except WalletOwnerUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wallet owner is unavailable.",
        ) from exc
    except WalletAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wallet with this currency already exists.",
        ) from exc
    except InvalidWalletCurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet currency.",
        ) from exc

    return _wallet_with_balance_to_response(wallet_with_balance)


@router.get(
    "/me",
    response_model=list[WalletWithBalanceResponse],
    status_code=status.HTTP_200_OK,
)
async def get_my_wallets(
    current_user: Annotated[User, Depends(get_current_user)],
    get_my_wallets_use_case: Annotated[
        GetMyWalletsUseCase,
        Depends(get_my_wallets_use_case),
    ],
) -> list[WalletWithBalanceResponse]:
    """Возвращает кошельки текущего пользователя.

    Args:
        current_user: Пользователь, полученный из JWT access token.
        get_my_wallets_use_case: Use case получения списка кошельков.

    Returns:
        Список кошельков текущего пользователя с проекциями балансов.
    """
    wallets = await get_my_wallets_use_case.execute(user_id=current_user.id)
    return [_wallet_with_balance_to_response(wallet) for wallet in wallets]


@router.get(
    "/{wallet_id}",
    response_model=WalletWithBalanceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_wallet_by_id(
    wallet_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    get_wallet_by_id_use_case: Annotated[
        GetWalletByIdUseCase,
        Depends(get_wallet_by_id_use_case),
    ],
) -> WalletWithBalanceResponse:
    """Возвращает кошелек текущего пользователя по id.

    Args:
        wallet_id: Идентификатор кошелька.
        current_user: Пользователь, полученный из JWT access token.
        get_wallet_by_id_use_case: Use case получения кошелька.

    Returns:
        Кошелек с проекцией баланса.

    Raises:
        HTTPException: Если кошелек не найден или принадлежит другому пользователю.
    """
    try:
        wallet_with_balance = await get_wallet_by_id_use_case.execute(
            user_id=current_user.id,
            wallet_id=wallet_id,
        )
    except WalletNotFoundError as exc:
        _raise_wallet_not_found(exc)

    return _wallet_with_balance_to_response(wallet_with_balance)
