"""Мапперы между доменными кошельками и SQLAlchemy-моделями."""

from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    Wallet,
    WalletStatus,
)
from payflow.modules.financial_core.infrastructure.models import (
    WalletBalanceModel,
    WalletModel,
)


def wallet_entity_to_model(wallet: Wallet) -> WalletModel:
    """Преобразует доменный кошелек в ORM-модель.

    Args:
        wallet: Доменная сущность кошелька.

    Returns:
        SQLAlchemy-модель кошелька.
    """
    return WalletModel(
        id=wallet.id,
        user_id=wallet.user_id,
        currency=wallet.currency,
        status=wallet.status.value,
        created_at=wallet.created_at,
        updated_at=wallet.updated_at,
    )


def wallet_model_to_entity(wallet_model: WalletModel) -> Wallet:
    """Преобразует ORM-модель кошелька в доменную сущность.

    Args:
        wallet_model: SQLAlchemy-модель кошелька.

    Returns:
        Доменная сущность кошелька.
    """
    return Wallet(
        id=wallet_model.id,
        user_id=wallet_model.user_id,
        currency=wallet_model.currency,
        status=WalletStatus(wallet_model.status),
        created_at=wallet_model.created_at,
        updated_at=wallet_model.updated_at,
    )


def balance_entity_to_model(balance: BalanceProjection) -> WalletBalanceModel:
    """Преобразует доменную проекцию баланса в ORM-модель.

    Args:
        balance: Доменная проекция баланса.

    Returns:
        SQLAlchemy-модель проекции баланса.
    """
    return WalletBalanceModel(
        wallet_id=balance.wallet_id,
        available_amount_minor=balance.available_amount_minor,
        locked_amount_minor=balance.locked_amount_minor,
        currency=balance.currency,
        updated_at=balance.updated_at,
    )


def balance_model_to_entity(balance_model: WalletBalanceModel) -> BalanceProjection:
    """Преобразует ORM-модель проекции баланса в доменную сущность.

    Args:
        balance_model: SQLAlchemy-модель проекции баланса.

    Returns:
        Доменная проекция баланса.
    """
    return BalanceProjection(
        wallet_id=balance_model.wallet_id,
        available_amount_minor=balance_model.available_amount_minor,
        locked_amount_minor=balance_model.locked_amount_minor,
        currency=balance_model.currency,
        updated_at=balance_model.updated_at,
    )
