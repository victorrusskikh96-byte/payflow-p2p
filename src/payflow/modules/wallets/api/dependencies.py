"""Dependency wiring для HTTP API модуля кошельков."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.core.database import get_async_session
from payflow.modules.outbox.application.repositories import OutboxEventRepository
from payflow.modules.outbox.infrastructure.repositories import (
    SQLAlchemyOutboxEventRepository,
)
from payflow.modules.users.application.repositories import UserRepository
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository
from payflow.modules.wallets.application import (
    CreateWalletUseCase,
    GetMyWalletsUseCase,
    GetWalletByIdUseCase,
    TransactionManager,
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.wallets.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)


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
) -> OutboxEventRepository:
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
        OutboxEventRepository,
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
