"""Use cases создания и чтения кошельков пользователя."""

from dataclasses import dataclass
from uuid import UUID

from payflow.modules.financial_core.application.events import (
    OutboxEventWriter,
    wallet_created_event,
)
from payflow.modules.financial_core.application.wallets.repositories import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.financial_core.application.wallets.transactions import (
    TransactionManager,
)
from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    Wallet,
    WalletAlreadyExistsError,
    WalletNotFoundError,
    WalletOwnerUnavailableError,
)
from payflow.modules.users.application.repositories import UserRepository
from payflow.modules.users.domain import UserStatus


@dataclass(frozen=True, slots=True)
class WalletWithBalance:
    """Хранит кошелек вместе с read-моделью баланса."""

    wallet: Wallet
    balance: BalanceProjection


class CreateWalletUseCase:
    """Создает кошелек пользователя и начальную проекцию баланса."""

    def __init__(
        self,
        *,
        users: UserRepository,
        wallets: WalletRepository,
        balances: WalletBalanceRepository,
        outbox_events: OutboxEventWriter,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case открытия кошелька.

        Args:
            users: Репозиторий пользователей.
            wallets: Репозиторий кошельков.
            balances: Репозиторий проекций балансов.
            outbox_events: Репозиторий outbox events.
            transaction_manager: Менеджер транзакции.
        """
        self._users = users
        self._wallets = wallets
        self._balances = balances
        self._outbox_events = outbox_events
        self._transaction_manager = transaction_manager

    async def execute(self, *, user_id: UUID, currency: str) -> WalletWithBalance:
        """Создает кошелек и нулевую проекцию баланса атомарно.

        Args:
            user_id: Идентификатор пользователя-владельца.
            currency: Код валюты нового кошелька.

        Returns:
            Созданный кошелек с проекцией баланса.

        Raises:
            WalletOwnerUnavailableError: Если пользователь не найден или заблокирован.
            WalletAlreadyExistsError: Если кошелек в такой валюте уже существует.
            InvalidWalletCurrencyError: Если валюта пустая после нормализации.
        """
        async with self._transaction_manager:
            user = await self._users.get_by_id(user_id)
            if user is None or user.status is UserStatus.BLOCKED:
                raise WalletOwnerUnavailableError("Wallet owner is unavailable.")

            if await self._wallets.exists_by_user_id_and_currency(user_id, currency):
                raise WalletAlreadyExistsError(
                    "Wallet with this currency already exists."
                )

            wallet = await self._wallets.create(
                Wallet(user_id=user_id, currency=currency)
            )
            balance = await self._balances.create_initial(
                BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
            )
            await self._outbox_events.create(
                wallet_created_event(
                    wallet_id=wallet.id,
                    user_id=wallet.user_id,
                    currency=wallet.currency,
                )
            )

            return WalletWithBalance(wallet=wallet, balance=balance)


class GetMyWalletsUseCase:
    """Возвращает кошельки текущего пользователя с проекциями балансов."""

    def __init__(
        self,
        *,
        wallets: WalletRepository,
        balances: WalletBalanceRepository,
    ) -> None:
        """Создает use case получения списка кошельков.

        Args:
            wallets: Репозиторий кошельков.
            balances: Репозиторий проекций балансов.
        """
        self._wallets = wallets
        self._balances = balances

    async def execute(self, *, user_id: UUID) -> list[WalletWithBalance]:
        """Возвращает кошельки пользователя с balance projection.

        Args:
            user_id: Идентификатор текущего пользователя.

        Returns:
            Список кошельков с проекциями балансов.
        """
        wallets = await self._wallets.get_by_user_id(user_id)
        return [await self._wallet_with_balance(wallet) for wallet in wallets]

    async def _wallet_with_balance(self, wallet: Wallet) -> WalletWithBalance:
        balance = await self._balances.get_by_wallet_id(wallet.id)
        if balance is None:
            balance = BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)
        return WalletWithBalance(wallet=wallet, balance=balance)


class GetWalletByIdUseCase:
    """Возвращает кошелек текущего пользователя по идентификатору."""

    def __init__(
        self,
        *,
        wallets: WalletRepository,
        balances: WalletBalanceRepository,
    ) -> None:
        """Создает use case получения кошелька по id.

        Args:
            wallets: Репозиторий кошельков.
            balances: Репозиторий проекций балансов.
        """
        self._wallets = wallets
        self._balances = balances

    async def execute(self, *, user_id: UUID, wallet_id: UUID) -> WalletWithBalance:
        """Возвращает кошелек, если он принадлежит текущему пользователю.

        Args:
            user_id: Идентификатор текущего пользователя.
            wallet_id: Идентификатор запрошенного кошелька.

        Returns:
            Кошелек с проекцией баланса.

        Raises:
            WalletNotFoundError: Если кошелек не найден или принадлежит другому
                пользователю.
        """
        wallet = await self._wallets.get_by_id(wallet_id)
        if wallet is None or wallet.user_id != user_id:
            raise WalletNotFoundError("Wallet was not found.")

        balance = await self._balances.get_by_wallet_id(wallet.id)
        if balance is None:
            balance = BalanceProjection(wallet_id=wallet.id, currency=wallet.currency)

        return WalletWithBalance(wallet=wallet, balance=balance)
