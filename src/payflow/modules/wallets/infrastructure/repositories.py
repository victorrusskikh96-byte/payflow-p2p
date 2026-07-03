"""SQLAlchemy-репозитории кошельков и проекций балансов."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.wallets.application.repositories import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.wallets.domain import BalanceProjection, Wallet, normalize_currency
from payflow.modules.wallets.infrastructure.mappers import (
    balance_entity_to_model,
    balance_model_to_entity,
    wallet_entity_to_model,
    wallet_model_to_entity,
)
from payflow.modules.wallets.infrastructure.models import (
    WalletBalanceModel,
    WalletModel,
)


class SQLAlchemyWalletRepository(WalletRepository):
    """Работает с кошельками через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий кошельков.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, wallet: Wallet) -> Wallet:
        """Сохраняет новый кошелек в базе данных.

        Args:
            wallet: Доменная сущность кошелька.

        Returns:
            Сохраненный кошелек.
        """
        wallet_model = wallet_entity_to_model(wallet)
        self._session.add(wallet_model)
        await self._session.flush()
        return wallet_model_to_entity(wallet_model)

    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        """Возвращает кошелек по идентификатору.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Кошелек или None, если запись не найдена.
        """
        wallet_model = await self._session.get(WalletModel, wallet_id)
        if wallet_model is None:
            return None
        return wallet_model_to_entity(wallet_model)

    async def get_by_user_id(self, user_id: UUID) -> list[Wallet]:
        """Возвращает кошельки пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список кошельков пользователя.
        """
        statement = (
            select(WalletModel)
            .where(WalletModel.user_id == user_id)
            .order_by(WalletModel.created_at, WalletModel.id)
        )
        result = await self._session.scalars(statement)
        return [wallet_model_to_entity(wallet_model) for wallet_model in result.all()]

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
            Кошелек или None, если запись не найдена.

        Raises:
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """
        normalized_currency = normalize_currency(currency)
        statement = select(WalletModel).where(
            WalletModel.user_id == user_id,
            WalletModel.currency == normalized_currency,
        )
        wallet_model = await self._session.scalar(statement)
        if wallet_model is None:
            return None
        return wallet_model_to_entity(wallet_model)

    async def exists_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> bool:
        """Проверяет наличие кошелька пользователя в указанной валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты кошелька.

        Returns:
            True, если кошелек найден.

        Raises:
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """
        normalized_currency = normalize_currency(currency)
        statement = select(
            exists().where(
                WalletModel.user_id == user_id,
                WalletModel.currency == normalized_currency,
            )
        )
        return bool(await self._session.scalar(statement))


class SQLAlchemyWalletBalanceRepository(WalletBalanceRepository):
    """Работает с проекциями балансов через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий проекций балансов.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create_initial(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет начальную проекцию баланса кошелька.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        balance_model = balance_entity_to_model(balance)
        self._session.add(balance_model)
        await self._session.flush()
        return balance_model_to_entity(balance_model)

    async def get_by_wallet_id(self, wallet_id: UUID) -> BalanceProjection | None:
        """Возвращает проекцию баланса по идентификатору кошелька.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Проекция баланса или None, если запись не найдена.
        """
        balance_model = await self._session.get(WalletBalanceModel, wallet_id)
        if balance_model is None:
            return None
        return balance_model_to_entity(balance_model)

    async def update(self, balance: BalanceProjection) -> BalanceProjection:
        """Обновляет сохраненную проекцию баланса кошелька.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Обновленная проекция баланса.
        """
        balance_model = await self._session.get(WalletBalanceModel, balance.wallet_id)
        if balance_model is None:
            balance_model = balance_entity_to_model(balance)
            self._session.add(balance_model)
        else:
            balance_model.available_amount_minor = balance.available_amount_minor
            balance_model.locked_amount_minor = balance.locked_amount_minor
            balance_model.currency = balance.currency
            balance_model.updated_at = balance.updated_at

        await self._session.flush()
        return balance_model_to_entity(balance_model)
