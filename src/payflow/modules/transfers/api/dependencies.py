"""Dependency wiring для HTTP API модуля P2P-переводов."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.core.database import get_async_session
from payflow.modules.ledger.application.repositories import (
    LedgerTransactionRepository,
)
from payflow.modules.ledger.infrastructure.repositories import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.transfers.application import (
    CreateP2PTransferUseCase,
    GetMyTransfersUseCase,
    GetTransferByIdUseCase,
    TransactionManager,
    TransferRepository,
)
from payflow.modules.transfers.infrastructure.repositories import (
    SQLAlchemyTransferRepository,
)
from payflow.modules.transfers.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.wallets.application import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.wallets.infrastructure.repositories import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)


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
        transaction_manager: Менеджер транзакций.

    Returns:
        Use case создания P2P-перевода.
    """
    return CreateP2PTransferUseCase(
        transfers=transfers,
        wallets=wallets,
        balances=balances,
        ledger_transactions=ledger_transactions,
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
