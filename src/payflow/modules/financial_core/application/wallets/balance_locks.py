"""Application helper для стабильной блокировки balance projection."""

from uuid import UUID

from payflow.modules.financial_core.application.wallets.repositories import (
    WalletBalanceRepository,
)
from payflow.modules.financial_core.domain.wallets import BalanceProjection


async def lock_two_wallet_balances_for_update(
    balances: WalletBalanceRepository,
    *,
    first_wallet_id: UUID,
    second_wallet_id: UUID,
) -> tuple[BalanceProjection, BalanceProjection]:
    """Блокирует две проекции балансов в детерминированном порядке.

    Args:
        balances: Репозиторий проекций балансов.
        first_wallet_id: Первый идентификатор кошелька в семантике операции.
        second_wallet_id: Второй идентификатор кошелька в семантике операции.

    Returns:
        Пара заблокированных балансов в порядке first, second.

    Raises:
        WalletBalanceNotFoundError: Если одна из проекций баланса не найдена.
    """
    locked_balances: dict[UUID, BalanceProjection] = {}
    for wallet_id in sorted(
        (first_wallet_id, second_wallet_id),
        key=lambda item: item.int,
    ):
        locked_balances[wallet_id] = await balances.get_by_wallet_id_for_update(
            wallet_id
        )

    return locked_balances[first_wallet_id], locked_balances[second_wallet_id]
