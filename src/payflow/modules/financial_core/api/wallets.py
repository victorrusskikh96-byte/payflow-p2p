"""HTTP API кошельков внутри Financial Core."""

from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.core.database import get_async_session
from payflow.modules.auth.api.dependencies import get_current_user
from payflow.modules.financial_core.application.events import (
    OutboxEventWriter,
)
from payflow.modules.financial_core.application.wallets import (
    CreateWalletUseCase,
    GetMyWalletsUseCase,
    GetWalletByIdUseCase,
    TransactionManager,
    WalletBalanceRepository,
    WalletRepository,
    WalletWithBalance,
)
from payflow.modules.financial_core.application.wallets.exceptions import (
    WalletsApplicationError,
)
from payflow.modules.financial_core.domain.wallets import (
    InvalidWalletCurrencyError,
    WalletAlreadyExistsError,
    WalletNotFoundError,
    WalletOwnerUnavailableError,
    WalletStatus,
)
from payflow.modules.financial_core.infrastructure.repositories.outbox import (
    SQLAlchemyOutboxEventRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.wallets import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.financial_core.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.application.repositories import UserRepository
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository

CurrencyField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=16),
]

router = APIRouter()


class CreateWalletRequest(BaseModel):
    """Описывает запрос на создание кошелька."""

    model_config = ConfigDict(json_schema_extra={"example": {"currency": "USD"}})

    currency: CurrencyField


class WalletResponse(BaseModel):
    """Описывает HTTP-представление кошелька."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "user_id": "11111111-1111-4111-8111-111111111111",
                "currency": "USD",
                "status": "ACTIVE",
                "created_at": "2026-07-18T10:15:30+00:00",
                "updated_at": "2026-07-18T10:15:30+00:00",
            }
        }
    )

    id: UUID
    user_id: UUID
    currency: str
    status: WalletStatus
    created_at: datetime
    updated_at: datetime


class WalletBalanceResponse(BaseModel):
    """Описывает HTTP-представление проекции баланса кошелька."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "wallet_id": "22222222-2222-4222-8222-222222222222",
                "available_amount_minor": 100000,
                "locked_amount_minor": 0,
                "currency": "USD",
                "updated_at": "2026-07-18T10:15:30+00:00",
            }
        }
    )

    wallet_id: UUID
    available_amount_minor: int
    locked_amount_minor: int
    currency: str
    updated_at: datetime


class WalletWithBalanceResponse(BaseModel):
    """Описывает HTTP-представление кошелька с проекцией баланса."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "wallet": {
                    "id": "22222222-2222-4222-8222-222222222222",
                    "user_id": "11111111-1111-4111-8111-111111111111",
                    "currency": "USD",
                    "status": "ACTIVE",
                    "created_at": "2026-07-18T10:15:30+00:00",
                    "updated_at": "2026-07-18T10:15:30+00:00",
                },
                "balance": {
                    "wallet_id": "22222222-2222-4222-8222-222222222222",
                    "available_amount_minor": 100000,
                    "locked_amount_minor": 0,
                    "currency": "USD",
                    "updated_at": "2026-07-18T10:15:30+00:00",
                },
            }
        }
    )

    wallet: WalletResponse
    balance: WalletBalanceResponse


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserRepository:
    """Создает репозиторий пользователей для wallet use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий пользователей.
    """
    return SQLAlchemyUserRepository(session)


def get_wallet_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WalletRepository:
    """Создает репозиторий кошельков для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий кошельков.
    """
    return SQLAlchemyWalletRepository(session)


def get_wallet_balance_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WalletBalanceRepository:
    """Создает репозиторий проекций балансов для текущего запроса.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий проекций балансов.
    """
    return SQLAlchemyWalletBalanceRepository(session)


def get_outbox_event_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OutboxEventWriter:
    """Создает репозиторий outbox events для wallet use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Репозиторий outbox events.
    """
    return SQLAlchemyOutboxEventRepository(session)


def get_transaction_manager(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TransactionManager:
    """Создает менеджер транзакций для wallet use cases.

    Args:
        session: Асинхронная SQLAlchemy-сессия текущего запроса.

    Returns:
        Менеджер транзакций SQLAlchemy.
    """
    return SQLAlchemyTransactionManager(session)


def get_create_wallet_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    wallets: Annotated[WalletRepository, Depends(get_wallet_repository)],
    balances: Annotated[
        WalletBalanceRepository,
        Depends(get_wallet_balance_repository),
    ],
    outbox_events: Annotated[
        OutboxEventWriter,
        Depends(get_outbox_event_repository),
    ],
    transaction_manager: Annotated[
        TransactionManager,
        Depends(get_transaction_manager),
    ],
) -> CreateWalletUseCase:
    """Собирает use case создания кошелька.

    Args:
        users: Репозиторий пользователей.
        wallets: Репозиторий кошельков.
        balances: Репозиторий проекций балансов.
        outbox_events: Репозиторий outbox events.
        transaction_manager: Менеджер транзакций.

    Returns:
        Use case создания кошелька.
    """
    return CreateWalletUseCase(
        users=users,
        wallets=wallets,
        balances=balances,
        outbox_events=outbox_events,
        transaction_manager=transaction_manager,
    )


def get_my_wallets_use_case(
    wallets: Annotated[WalletRepository, Depends(get_wallet_repository)],
    balances: Annotated[
        WalletBalanceRepository,
        Depends(get_wallet_balance_repository),
    ],
) -> GetMyWalletsUseCase:
    """Собирает use case получения кошельков текущего пользователя.

    Args:
        wallets: Репозиторий кошельков.
        balances: Репозиторий проекций балансов.

    Returns:
        Use case получения списка кошельков.
    """
    return GetMyWalletsUseCase(wallets=wallets, balances=balances)


def get_wallet_by_id_use_case(
    wallets: Annotated[WalletRepository, Depends(get_wallet_repository)],
    balances: Annotated[
        WalletBalanceRepository,
        Depends(get_wallet_balance_repository),
    ],
) -> GetWalletByIdUseCase:
    """Собирает use case получения кошелька по id.

    Args:
        wallets: Репозиторий кошельков.
        balances: Репозиторий проекций балансов.

    Returns:
        Use case получения кошелька по id.
    """
    return GetWalletByIdUseCase(wallets=wallets, balances=balances)


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
    summary="Создать кошелек",
    description=(
        "Создает кошелек текущего пользователя в указанной валюте и возвращает "
        "данные кошелька отдельно от balance projection."
    ),
    operation_id="create_wallet",
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
    except WalletsApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet operation failed.",
        ) from exc

    return _wallet_with_balance_to_response(wallet_with_balance)


@router.get(
    "/me",
    response_model=list[WalletWithBalanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить мои кошельки",
    description=(
        "Возвращает список кошельков текущего пользователя с отдельной "
        "проекцией баланса для каждого кошелька."
    ),
    operation_id="get_my_wallets",
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
    summary="Получить мой кошелек по id",
    description=(
        "Возвращает кошелек текущего пользователя по идентификатору. Чужие "
        "и отсутствующие кошельки отвечают одинаковым безопасным 404."
    ),
    operation_id="get_wallet_by_id",
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
