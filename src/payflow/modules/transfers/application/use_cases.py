"""Application use cases пользовательских P2P-переводов."""

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
from payflow.modules.outbox.application.event_factory import OutboxEventFactory
from payflow.modules.outbox.application.repositories import OutboxEventRepository
from payflow.modules.transfers.application.exceptions import (
    InactiveTransferWalletError,
    InsufficientTransferFundsError,
    RecipientWalletNotFoundError,
    SenderWalletNotFoundError,
    TransferWalletCurrencyMismatchError,
    TransferWalletOwnershipError,
)
from payflow.modules.transfers.application.repositories import TransferRepository
from payflow.modules.transfers.application.transactions import TransactionManager
from payflow.modules.transfers.domain import (
    DuplicateTransferOperationError,
    InvalidTransferAmountError,
    InvalidTransferCurrencyError,
    SameTransferWalletsError,
    Transfer,
    TransferNotFoundError,
)
from payflow.modules.wallets.application.repositories import (
    WalletBalanceRepository,
    WalletRepository,
)
from payflow.modules.wallets.domain import BalanceProjection, Wallet, WalletStatus


@dataclass(frozen=True, slots=True)
class P2PTransferResult:
    """Хранит результат успешного пользовательского P2P-перевода."""

    transfer: Transfer
    transaction: LedgerTransaction
    sender_balance: BalanceProjection
    recipient_balance: BalanceProjection


class CreateP2PTransferUseCase:
    """Выполняет пользовательский P2P-перевод через ledger и balance projection."""

    def __init__(
        self,
        *,
        transfers: TransferRepository,
        wallets: WalletRepository,
        balances: WalletBalanceRepository,
        ledger_transactions: LedgerTransactionRepository,
        outbox_events: OutboxEventRepository,
        transaction_manager: TransactionManager,
    ) -> None:
        """Создает use case P2P-перевода.

        Args:
            transfers: Репозиторий P2P-переводов.
            wallets: Репозиторий кошельков.
            balances: Репозиторий проекций балансов.
            ledger_transactions: Репозиторий ledger transactions.
            outbox_events: Репозиторий outbox events.
            transaction_manager: Менеджер транзакции БД.
        """
        self._transfers = transfers
        self._wallets = wallets
        self._balances = balances
        self._ledger_transactions = ledger_transactions
        self._outbox_events = outbox_events
        self._transaction_manager = transaction_manager

    async def execute(
        self,
        *,
        operation_id: UUID,
        sender_user_id: UUID,
        sender_wallet_id: UUID,
        recipient_wallet_id: UUID,
        amount_minor: int,
        currency: str,
    ) -> P2PTransferResult:
        """Выполняет P2P-перевод атомарно с ledger transaction и balances.

        Args:
            operation_id: Идентификатор бизнес-операции перевода.
            sender_user_id: Идентификатор пользователя-отправителя.
            sender_wallet_id: Идентификатор кошелька отправителя.
            recipient_wallet_id: Идентификатор кошелька получателя.
            amount_minor: Сумма перевода в минорных единицах.
            currency: Валюта перевода.

        Returns:
            Результат операции с transfer, ledger transaction и балансами.

        Raises:
            InvalidTransferAmountError: Если amount_minor не больше нуля.
            InvalidTransferCurrencyError: Если валюта пустая после нормализации.
            SameTransferWalletsError: Если sender и recipient wallets совпадают.
            DuplicateTransferOperationError: Если operation_id уже существует.
            SenderWalletNotFoundError: Если кошелек отправителя не найден.
            RecipientWalletNotFoundError: Если кошелек получателя не найден.
            TransferWalletOwnershipError: Если sender wallet принадлежит другому
                пользователю.
            InactiveTransferWalletError: Если один из кошельков не ACTIVE.
            TransferWalletCurrencyMismatchError: Если валюты не совпадают.
            InsufficientTransferFundsError: Если средств отправителя недостаточно.
            WalletBalanceNotFoundError: Если balance projection не найдена.
        """
        self._validate_amount(amount_minor)
        self._validate_wallets(sender_wallet_id, recipient_wallet_id)
        normalized_currency = self._normalize_currency(currency)

        async with self._transaction_manager:
            if await self._transfers.exists_by_operation_id(operation_id):
                raise DuplicateTransferOperationError(
                    "Transfer operation already exists."
                )

            sender_wallet = await self._get_sender_wallet(
                wallet_id=sender_wallet_id,
                sender_user_id=sender_user_id,
            )
            recipient_wallet = await self._get_recipient_wallet(recipient_wallet_id)
            self._ensure_wallets_are_active(sender_wallet, recipient_wallet)
            self._ensure_wallet_currencies_match(
                sender_wallet=sender_wallet,
                recipient_wallet=recipient_wallet,
                currency=normalized_currency,
            )

            sender_balance, recipient_balance = await self._lock_balances(
                sender_wallet_id=sender_wallet_id,
                recipient_wallet_id=recipient_wallet_id,
            )
            self._ensure_balance_currencies_match(
                sender_balance=sender_balance,
                recipient_balance=recipient_balance,
                currency=normalized_currency,
            )

            if not sender_balance.has_sufficient_available_balance(amount_minor):
                raise InsufficientTransferFundsError(
                    "Sender wallet available balance is insufficient."
                )

            transfer = await self._transfers.create(
                Transfer(
                    operation_id=operation_id,
                    sender_user_id=sender_user_id,
                    sender_wallet_id=sender_wallet_id,
                    recipient_wallet_id=recipient_wallet_id,
                    amount_minor=amount_minor,
                    currency=normalized_currency,
                )
            )
            transaction = await self._ledger_transactions.create(
                self._build_ledger_transaction(
                    operation_id=operation_id,
                    sender_wallet_id=sender_wallet_id,
                    recipient_wallet_id=recipient_wallet_id,
                    amount_minor=amount_minor,
                    currency=normalized_currency,
                )
            )

            sender_balance.decrease_available_amount(amount_minor)
            recipient_balance.increase_available_amount(amount_minor)
            sender_balance = await self._balances.save(sender_balance)
            recipient_balance = await self._balances.save(recipient_balance)

            transfer.complete(ledger_transaction_id=transaction.id)
            transfer = await self._transfers.save_status(transfer)
            await self._outbox_events.create(
                OutboxEventFactory.p2p_transfer_completed(
                    transfer_id=transfer.id,
                    operation_id=operation_id,
                    sender_user_id=sender_user_id,
                    sender_wallet_id=sender_wallet_id,
                    recipient_wallet_id=recipient_wallet_id,
                    ledger_transaction_id=transaction.id,
                    amount_minor=amount_minor,
                    currency=normalized_currency,
                )
            )

            return P2PTransferResult(
                transfer=transfer,
                transaction=transaction,
                sender_balance=sender_balance,
                recipient_balance=recipient_balance,
            )

    async def _get_sender_wallet(
        self,
        *,
        wallet_id: UUID,
        sender_user_id: UUID,
    ) -> Wallet:
        wallet = await self._wallets.get_by_id(wallet_id)
        if wallet is None:
            raise SenderWalletNotFoundError("Sender wallet was not found.")
        if wallet.user_id != sender_user_id:
            raise TransferWalletOwnershipError("Sender wallet belongs to another user.")
        return wallet

    async def _get_recipient_wallet(self, wallet_id: UUID) -> Wallet:
        wallet = await self._wallets.get_by_id(wallet_id)
        if wallet is None:
            raise RecipientWalletNotFoundError("Recipient wallet was not found.")
        return wallet

    async def _lock_balances(
        self,
        *,
        sender_wallet_id: UUID,
        recipient_wallet_id: UUID,
    ) -> tuple[BalanceProjection, BalanceProjection]:
        locked_balances: dict[UUID, BalanceProjection] = {}
        for wallet_id in sorted((sender_wallet_id, recipient_wallet_id), key=str):
            locked_balances[
                wallet_id
            ] = await self._balances.get_by_wallet_id_for_update(wallet_id)

        return locked_balances[sender_wallet_id], locked_balances[recipient_wallet_id]

    @staticmethod
    def _validate_amount(amount_minor: int) -> None:
        if amount_minor <= 0:
            raise InvalidTransferAmountError("Transfer amount must be positive.")

    @staticmethod
    def _validate_wallets(sender_wallet_id: UUID, recipient_wallet_id: UUID) -> None:
        if sender_wallet_id == recipient_wallet_id:
            raise SameTransferWalletsError(
                "Transfer sender and recipient wallets must differ.",
            )

    @staticmethod
    def _normalize_currency(currency: str) -> str:
        normalized_currency = currency.strip().upper()
        if not normalized_currency:
            raise InvalidTransferCurrencyError("Transfer currency cannot be empty.")
        return normalized_currency

    @staticmethod
    def _ensure_wallets_are_active(
        sender_wallet: Wallet,
        recipient_wallet: Wallet,
    ) -> None:
        if (
            sender_wallet.status is not WalletStatus.ACTIVE
            or recipient_wallet.status is not WalletStatus.ACTIVE
        ):
            raise InactiveTransferWalletError("Transfer wallets must be active.")

    @staticmethod
    def _ensure_wallet_currencies_match(
        *,
        sender_wallet: Wallet,
        recipient_wallet: Wallet,
        currency: str,
    ) -> None:
        if sender_wallet.currency != currency or recipient_wallet.currency != currency:
            raise TransferWalletCurrencyMismatchError(
                "Wallet currencies must match transfer currency."
            )

    @staticmethod
    def _ensure_balance_currencies_match(
        *,
        sender_balance: BalanceProjection,
        recipient_balance: BalanceProjection,
        currency: str,
    ) -> None:
        if (
            sender_balance.currency != currency
            or recipient_balance.currency != currency
        ):
            raise TransferWalletCurrencyMismatchError(
                "Balance currencies must match transfer currency."
            )

    @staticmethod
    def _build_ledger_transaction(
        *,
        operation_id: UUID,
        sender_wallet_id: UUID,
        recipient_wallet_id: UUID,
        amount_minor: int,
        currency: str,
    ) -> LedgerTransaction:
        transaction_id = uuid4()
        return LedgerTransaction(
            id=transaction_id,
            operation_id=operation_id,
            operation_type=LedgerOperationType.P2P_TRANSFER,
            entries=(
                LedgerEntry(
                    transaction_id=transaction_id,
                    wallet_id=sender_wallet_id,
                    direction=LedgerEntryDirection.DEBIT,
                    amount_minor=amount_minor,
                    currency=currency,
                ),
                LedgerEntry(
                    transaction_id=transaction_id,
                    wallet_id=recipient_wallet_id,
                    direction=LedgerEntryDirection.CREDIT,
                    amount_minor=amount_minor,
                    currency=currency,
                ),
            ),
        )


class GetMyTransfersUseCase:
    """Возвращает P2P-переводы текущего пользователя."""

    def __init__(self, *, transfers: TransferRepository) -> None:
        """Создает use case получения списка P2P-переводов.

        Args:
            transfers: Репозиторий P2P-переводов.
        """
        self._transfers = transfers

    async def execute(self, *, sender_user_id: UUID) -> list[Transfer]:
        """Возвращает P2P-переводы отправителя.

        Args:
            sender_user_id: Идентификатор текущего пользователя.

        Returns:
            Список P2P-переводов текущего пользователя.
        """
        return await self._transfers.get_by_sender_user_id(sender_user_id)


class GetTransferByIdUseCase:
    """Возвращает P2P-перевод текущего пользователя по идентификатору."""

    def __init__(self, *, transfers: TransferRepository) -> None:
        """Создает use case получения P2P-перевода.

        Args:
            transfers: Репозиторий P2P-переводов.
        """
        self._transfers = transfers

    async def execute(self, *, sender_user_id: UUID, transfer_id: UUID) -> Transfer:
        """Возвращает P2P-перевод, если он принадлежит текущему пользователю.

        Args:
            sender_user_id: Идентификатор текущего пользователя.
            transfer_id: Идентификатор P2P-перевода.

        Returns:
            P2P-перевод текущего пользователя.

        Raises:
            TransferNotFoundError: Если перевод не найден или принадлежит другому
                пользователю.
        """
        transfer = await self._transfers.get_by_id(transfer_id)
        if transfer is None or transfer.sender_user_id != sender_user_id:
            raise TransferNotFoundError("Transfer was not found.")

        return transfer
