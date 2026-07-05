"""Application use cases внутренних платежных операций."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from payflow.modules.ledger.application.repositories import (
    LedgerTransactionRepository,
)
from payflow.modules.ledger.domain import (
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
)
from payflow.modules.payments.application.exceptions import (
    DuplicateInternalDepositOperationError,
    InsufficientSourceFundsError,
    InternalDepositWalletUnavailableError,
    InvalidInternalDepositAmountError,
    SourceWalletEqualsTargetWalletError,
    WalletCurrencyMismatchError,
)
from payflow.modules.payments.application.transactions import TransactionManager
from payflow.modules.wallets.application.repositories import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.wallets.domain import (
    BalanceProjection,
    Wallet,
    WalletNotFoundError,
    WalletStatus,
    normalize_currency,
)


@dataclass(frozen=True, slots=True)
class InternalDepositResult:
    """Хранит результат успешного internal deposit."""

    transaction: LedgerTransaction
    source_balance: BalanceProjection
    target_balance: BalanceProjection


class InternalDepositUseCase:
    """Выполняет внутреннее пополнение кошелька через funding wallet."""

    def __init__(
        self,
        *,
        wallets: WalletRepository,
        balances: WalletBalanceRepository,
        ledger_transactions: LedgerTransactionRepository,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case internal deposit.

        Args:
            wallets: Репозиторий кошельков.
            balances: Репозиторий проекций балансов.
            ledger_transactions: Репозиторий ledger transactions.
            transaction_manager: Менеджер транзакции БД.
        """
        self._wallets = wallets
        self._balances = balances
        self._ledger_transactions = ledger_transactions
        self._transaction_manager = transaction_manager

    async def execute(
        self,
        *,
        operation_id: UUID,
        source_wallet_id: UUID,
        target_wallet_id: UUID,
        amount_minor: int,
        currency: str,
    ) -> InternalDepositResult:
        """Выполняет internal deposit атомарно с ledger transaction.

        Args:
            operation_id: Идентификатор внутренней операции.
            source_wallet_id: Идентификатор funding wallet.
            target_wallet_id: Идентификатор пользовательского wallet.
            amount_minor: Сумма пополнения в минорных единицах.
            currency: Валюта операции.

        Returns:
            Результат операции с ledger transaction и обновленными балансами.

        Raises:
            InvalidInternalDepositAmountError: Если amount_minor не больше нуля.
            SourceWalletEqualsTargetWalletError: Если source и target совпадают.
            DuplicateInternalDepositOperationError: Если operation_id уже существует.
            WalletNotFoundError: Если source или target wallet не найден.
            InternalDepositWalletUnavailableError: Если кошелек не ACTIVE.
            WalletCurrencyMismatchError: Если валюты кошельков или команды не совпали.
            InsufficientSourceFundsError: Если funding wallet не имеет средств.
            WalletBalanceNotFoundError: Если balance projection не найдена.
        """
        if amount_minor <= 0:
            raise InvalidInternalDepositAmountError(
                "Internal deposit amount must be positive."
            )
        if source_wallet_id == target_wallet_id:
            raise SourceWalletEqualsTargetWalletError(
                "Source wallet must differ from target wallet."
            )

        normalized_currency = normalize_currency(currency)

        async with self._transaction_manager:
            if await self._ledger_transactions.exists_by_operation_id(operation_id):
                raise DuplicateInternalDepositOperationError(
                    "Internal deposit operation already exists."
                )

            source_wallet = await self._get_active_wallet(source_wallet_id)
            target_wallet = await self._get_active_wallet(target_wallet_id)
            self._ensure_wallet_currencies_match(
                source_wallet=source_wallet,
                target_wallet=target_wallet,
                currency=normalized_currency,
            )

            source_balance, target_balance = await self._lock_balances(
                source_wallet_id=source_wallet_id,
                target_wallet_id=target_wallet_id,
            )
            self._ensure_balance_currencies_match(
                source_balance=source_balance,
                target_balance=target_balance,
                currency=normalized_currency,
            )

            if not source_balance.has_sufficient_available_balance(amount_minor):
                raise InsufficientSourceFundsError(
                    "Source wallet available balance is insufficient."
                )

            transaction = await self._ledger_transactions.create(
                self._build_ledger_transaction(
                    operation_id=operation_id,
                    source_wallet_id=source_wallet_id,
                    target_wallet_id=target_wallet_id,
                    amount_minor=amount_minor,
                    currency=normalized_currency,
                )
            )

            source_balance.decrease_available_amount(amount_minor)
            target_balance.increase_available_amount(amount_minor)
            source_balance = await self._balances.save(source_balance)
            target_balance = await self._balances.save(target_balance)

            return InternalDepositResult(
                transaction=transaction,
                source_balance=source_balance,
                target_balance=target_balance,
            )

    async def _get_active_wallet(self, wallet_id: UUID) -> Wallet:
        wallet = await self._wallets.get_by_id(wallet_id)
        if wallet is None:
            raise WalletNotFoundError("Wallet was not found.")
        if wallet.status is not WalletStatus.ACTIVE:
            raise InternalDepositWalletUnavailableError("Wallet is not active.")
        return wallet

    async def _lock_balances(
        self,
        *,
        source_wallet_id: UUID,
        target_wallet_id: UUID,
    ) -> tuple[BalanceProjection, BalanceProjection]:
        locked_balances: dict[UUID, BalanceProjection] = {}
        for wallet_id in sorted((source_wallet_id, target_wallet_id), key=str):
            locked_balances[
                wallet_id
            ] = await self._balances.get_by_wallet_id_for_update(wallet_id)

        return locked_balances[source_wallet_id], locked_balances[target_wallet_id]

    @staticmethod
    def _ensure_wallet_currencies_match(
        *,
        source_wallet: Wallet,
        target_wallet: Wallet,
        currency: str,
    ) -> None:
        if source_wallet.currency != currency or target_wallet.currency != currency:
            raise WalletCurrencyMismatchError(
                "Wallet currencies must match operation currency."
            )

    @staticmethod
    def _ensure_balance_currencies_match(
        *,
        source_balance: BalanceProjection,
        target_balance: BalanceProjection,
        currency: str,
    ) -> None:
        if source_balance.currency != currency or target_balance.currency != currency:
            raise WalletCurrencyMismatchError(
                "Balance currencies must match operation currency."
            )

    @staticmethod
    def _build_ledger_transaction(
        *,
        operation_id: UUID,
        source_wallet_id: UUID,
        target_wallet_id: UUID,
        amount_minor: int,
        currency: str,
    ) -> LedgerTransaction:
        transaction_id = uuid4()
        return LedgerTransaction(
            id=transaction_id,
            operation_id=operation_id,
            operation_type=LedgerOperationType.INTERNAL_DEPOSIT,
            entries=(
                LedgerEntry(
                    transaction_id=transaction_id,
                    wallet_id=source_wallet_id,
                    direction=LedgerEntryDirection.DEBIT,
                    amount_minor=amount_minor,
                    currency=currency,
                ),
                LedgerEntry(
                    transaction_id=transaction_id,
                    wallet_id=target_wallet_id,
                    direction=LedgerEntryDirection.CREDIT,
                    amount_minor=amount_minor,
                    currency=currency,
                ),
            ),
        )
