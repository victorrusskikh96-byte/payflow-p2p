"""SQLAlchemy-репозитории кошельков и проекций балансов."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.financial_core.application.wallets.repositories import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    InvalidBalanceUpdateError,
    Wallet,
    WalletAlreadyExistsError,
    WalletBalanceNotFoundError,
    WalletNotFoundError,
    normalize_currency,
)
from payflow.modules.financial_core.infrastructure.mappers.wallets import (
    balance_entity_to_model,
    balance_model_to_entity,
    wallet_entity_to_model,
    wallet_model_to_entity,
)
from payflow.modules.financial_core.infrastructure.models import (
    WalletBalanceModel,
    WalletModel,
)

_WALLET_USER_ID_CURRENCY_UNIQUE_CONSTRAINT = "uq_wallets_user_id_currency"


def _violates_constraint(error: IntegrityError, constraint_name: str) -> bool:
    original_error = error.orig
    diagnostic = getattr(original_error, "diag", None)
    diagnostic_constraint = getattr(diagnostic, "constraint_name", None)
    if (
        isinstance(diagnostic_constraint, str)
        and diagnostic_constraint == constraint_name
    ):
        return True
    return constraint_name in str(original_error) or constraint_name in str(error)


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

        Raises:
            WalletAlreadyExistsError: Если кошелек в такой валюте уже существует.
            sqlalchemy.exc.IntegrityError: Если база данных отклоняет другие
                ограничения.
        """
        wallet_model = wallet_entity_to_model(wallet)
        self._session.add(wallet_model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _violates_constraint(
                exc,
                _WALLET_USER_ID_CURRENCY_UNIQUE_CONSTRAINT,
            ):
                raise WalletAlreadyExistsError(
                    "Wallet with this currency already exists."
                ) from exc
            raise
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

        Raises:
            InvalidBalanceUpdateError: Если валюта баланса не совпадает с валютой
                кошелька.
            WalletNotFoundError: Если кошелек для проекции не найден.
        """
        await self._ensure_currency_matches_wallet(balance)
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

    async def get_by_wallet_id_for_update(
        self,
        wallet_id: UUID,
    ) -> BalanceProjection:
        """Возвращает проекцию баланса с PostgreSQL row-level lock.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Заблокированная проекция баланса.

        Raises:
            WalletBalanceNotFoundError: Если запись проекции баланса не найдена.
        """
        statement = (
            select(WalletBalanceModel)
            .where(WalletBalanceModel.wallet_id == wallet_id)
            .with_for_update()
        )
        balance_model = await self._session.scalar(statement)
        if balance_model is None:
            raise WalletBalanceNotFoundError("Wallet balance was not found.")
        return balance_model_to_entity(balance_model)

    async def increase_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Увеличивает и сохраняет доступный баланс.

        Args:
            balance: Загруженная проекция баланса.
            amount_minor: Сумма увеличения в минорных единицах.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            InvalidBalanceUpdateError: Если обновление некорректно.
            WalletBalanceNotFoundError: Если запись проекции баланса не найдена.
        """
        balance.increase_available_amount(amount_minor)
        return await self.save(balance)

    async def decrease_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Уменьшает и сохраняет доступный баланс.

        Args:
            balance: Загруженная проекция баланса.
            amount_minor: Сумма уменьшения в минорных единицах.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            InsufficientFundsError: Если доступного баланса недостаточно.
            InvalidBalanceUpdateError: Если обновление некорректно.
            WalletBalanceNotFoundError: Если запись проекции баланса не найдена.
        """
        balance.decrease_available_amount(amount_minor)
        return await self.save(balance)

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
            WalletBalanceNotFoundError: Если запись проекции баланса не найдена.
        """
        balance = await self.get_by_wallet_id(wallet_id)
        if balance is None:
            raise WalletBalanceNotFoundError("Wallet balance was not found.")
        return balance.has_sufficient_available_balance(amount_minor)

    async def save(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет обновленную проекцию баланса кошелька.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Сохраненная проекция баланса.

        Raises:
            InvalidBalanceUpdateError: Если проекция нарушает инварианты или ее
                валюта не совпадает с валютой кошелька.
            WalletBalanceNotFoundError: Если запись проекции баланса не найдена.
            WalletNotFoundError: Если кошелек для проекции не найден.
        """
        balance.validate()
        await self._ensure_currency_matches_wallet(balance)

        balance_model = await self._session.get(WalletBalanceModel, balance.wallet_id)
        if balance_model is None:
            raise WalletBalanceNotFoundError("Wallet balance was not found.")

        balance_model.available_amount_minor = balance.available_amount_minor
        balance_model.locked_amount_minor = balance.locked_amount_minor
        balance_model.currency = balance.currency
        balance_model.updated_at = balance.updated_at

        await self._session.flush()
        return balance_model_to_entity(balance_model)

    async def update(self, balance: BalanceProjection) -> BalanceProjection:
        """Обновляет сохраненную проекцию баланса кошелька.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Обновленная проекция баланса.

        Raises:
            InvalidBalanceUpdateError: Если проекция нарушает инварианты.
            WalletBalanceNotFoundError: Если запись проекции баланса не найдена.
        """
        return await self.save(balance)

    async def _ensure_currency_matches_wallet(
        self,
        balance: BalanceProjection,
    ) -> None:
        wallet_currency = await self._session.scalar(
            select(WalletModel.currency).where(WalletModel.id == balance.wallet_id)
        )
        if wallet_currency is None:
            raise WalletNotFoundError("Wallet was not found.")

        normalized_wallet_currency = normalize_currency(wallet_currency)
        normalized_balance_currency = normalize_currency(balance.currency)
        if normalized_balance_currency != normalized_wallet_currency:
            raise InvalidBalanceUpdateError(
                "Balance currency must match wallet currency."
            )
        balance.currency = normalized_balance_currency
