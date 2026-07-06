"""Интерфейсы репозиториев для кошельков и проекций балансов."""

from typing import Protocol
from uuid import UUID

from payflow.modules.financial_core.domain.wallets import BalanceProjection, Wallet


class WalletRepository(Protocol):
    """Определяет контракт хранилища кошельков для application layer."""

    async def create(self, wallet: Wallet) -> Wallet:
        """Сохраняет новый кошелек.

        Args:
            wallet: Доменная сущность кошелька.

        Returns:
            Сохраненный кошелек.
        """

    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        """Возвращает кошелек по идентификатору.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Кошелек или None, если он не найден.
        """

    async def get_by_user_id(self, user_id: UUID) -> list[Wallet]:
        """Возвращает кошельки пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список кошельков пользователя.
        """

    async def get_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> Wallet | None:
        """Возвращает кошелек пользователя в указанной валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты кошелька.

        Returns:
            Кошелек или None, если он не найден.

        Raises:
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """

    async def exists_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> bool:
        """Проверяет существование кошелька пользователя в указанной валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты кошелька.

        Returns:
            True, если кошелек существует.

        Raises:
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """


class WalletBalanceRepository(Protocol):
    """Определяет контракт хранилища проекций балансов кошельков."""

    async def create_initial(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет начальную проекцию баланса кошелька.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """

    async def get_by_wallet_id(self, wallet_id: UUID) -> BalanceProjection | None:
        """Возвращает проекцию баланса по идентификатору кошелька.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Проекция баланса или None, если она не найдена.
        """

    async def get_by_wallet_id_for_update(
        self,
        wallet_id: UUID,
    ) -> BalanceProjection:
        """Возвращает проекцию баланса с row-level lock.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Заблокированная проекция баланса.

        Raises:
            WalletBalanceNotFoundError: Если проекция баланса не найдена.
        """

    async def increase_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Увеличивает и сохраняет доступный баланс.

        Args:
            balance: Заблокированная или загруженная проекция баланса.
            amount_minor: Сумма увеличения в минорных единицах.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            InvalidBalanceUpdateError: Если обновление некорректно.
            WalletBalanceNotFoundError: Если проекция баланса не найдена.
        """

    async def decrease_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Уменьшает и сохраняет доступный баланс.

        Args:
            balance: Заблокированная или загруженная проекция баланса.
            amount_minor: Сумма уменьшения в минорных единицах.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            InsufficientFundsError: Если доступного баланса недостаточно.
            InvalidBalanceUpdateError: Если обновление некорректно.
            WalletBalanceNotFoundError: Если проекция баланса не найдена.
        """

    async def has_sufficient_available_balance(
        self,
        wallet_id: UUID,
        amount_minor: int,
    ) -> bool:
        """Проверяет достаточность доступного баланса кошелька.

        Args:
            wallet_id: Идентификатор кошелька.
            amount_minor: Проверяемая сумма в минорных единицах.

        Returns:
            True, если доступного баланса достаточно.

        Raises:
            InvalidBalanceUpdateError: Если проверяемая сумма отрицательная.
            WalletBalanceNotFoundError: Если проекция баланса не найдена.
        """

    async def save(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет обновленную проекцию баланса.

        Args:
            balance: Обновленная доменная проекция баланса.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            InvalidBalanceUpdateError: Если проекция нарушает инварианты.
            WalletBalanceNotFoundError: Если проекция баланса не найдена.
        """

    async def update(self, balance: BalanceProjection) -> BalanceProjection:
        """Обновляет сохраненную проекцию баланса кошелька.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Обновленная проекция баланса.

        Raises:
            InvalidBalanceUpdateError: Если проекция нарушает инварианты.
            WalletBalanceNotFoundError: Если проекция баланса не найдена.
        """
