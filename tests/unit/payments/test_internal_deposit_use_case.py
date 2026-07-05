"""Unit-тесты use case внутреннего пополнения кошелька."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from payflow.modules.ledger.domain import (
    LedgerEntry,
    LedgerEntryDirection,
    LedgerOperationType,
    LedgerTransaction,
)
from payflow.modules.payments.application.exceptions import (
    DuplicateInternalDepositOperationError,
    InsufficientSourceFundsError,
    InvalidInternalDepositAmountError,
    SourceWalletEqualsTargetWalletError,
    WalletCurrencyMismatchError,
)
from payflow.modules.payments.application.use_cases import InternalDepositUseCase
from payflow.modules.wallets.domain import (
    BalanceProjection,
    Wallet,
    WalletStatus,
)


class InMemoryWalletRepository:
    """Хранит кошельки в памяти для unit-тестов."""

    def __init__(self, wallets: list[Wallet]) -> None:
        """Создает repository с заданными кошельками.

        Args:
            wallets: Кошельки, доступные для теста.
        """
        self.wallets = {wallet.id: wallet for wallet in wallets}

    async def create(self, wallet: Wallet) -> Wallet:
        """Сохраняет кошелек в памяти.

        Args:
            wallet: Доменная сущность кошелька.

        Returns:
            Сохраненный кошелек.
        """
        self.wallets[wallet.id] = wallet
        return wallet

    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        """Возвращает кошелек по id.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Кошелек или None.
        """
        return self.wallets.get(wallet_id)

    async def get_by_user_id(self, user_id: UUID) -> list[Wallet]:
        """Возвращает кошельки пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список кошельков пользователя.
        """
        return [wallet for wallet in self.wallets.values() if wallet.user_id == user_id]

    async def get_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> Wallet | None:
        """Возвращает кошелек пользователя в валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты.

        Returns:
            Кошелек или None.
        """
        normalized_currency = currency.strip().upper()
        for wallet in self.wallets.values():
            if wallet.user_id == user_id and wallet.currency == normalized_currency:
                return wallet
        return None

    async def exists_by_user_id_and_currency(
        self,
        user_id: UUID,
        currency: str,
    ) -> bool:
        """Проверяет наличие кошелька пользователя в валюте.

        Args:
            user_id: Идентификатор пользователя.
            currency: Код валюты.

        Returns:
            True, если кошелек существует.
        """
        return await self.get_by_user_id_and_currency(user_id, currency) is not None


class InMemoryWalletBalanceRepository:
    """Хранит проекции балансов в памяти для unit-тестов."""

    def __init__(self, balances: list[BalanceProjection]) -> None:
        """Создает repository с заданными балансами.

        Args:
            balances: Проекции балансов, доступные для теста.
        """
        self.balances = {balance.wallet_id: balance for balance in balances}
        self.locked_wallet_ids: list[UUID] = []

    async def create_initial(
        self,
        balance: BalanceProjection,
    ) -> BalanceProjection:
        """Сохраняет начальную проекцию баланса.

        Args:
            balance: Доменная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        self.balances[balance.wallet_id] = balance
        return balance

    async def get_by_wallet_id(self, wallet_id: UUID) -> BalanceProjection | None:
        """Возвращает баланс по wallet_id.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Проекция баланса или None.
        """
        return self.balances.get(wallet_id)

    async def get_by_wallet_id_for_update(
        self,
        wallet_id: UUID,
    ) -> BalanceProjection:
        """Возвращает баланс и отмечает row lock.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Проекция баланса.
        """
        self.locked_wallet_ids.append(wallet_id)
        return self.balances[wallet_id]

    async def increase_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Увеличивает доступный баланс.

        Args:
            balance: Проекция баланса.
            amount_minor: Сумма увеличения.

        Returns:
            Обновленная проекция баланса.
        """
        balance.increase_available_amount(amount_minor)
        return await self.save(balance)

    async def decrease_available_amount(
        self,
        balance: BalanceProjection,
        amount_minor: int,
    ) -> BalanceProjection:
        """Уменьшает доступный баланс.

        Args:
            balance: Проекция баланса.
            amount_minor: Сумма уменьшения.

        Returns:
            Обновленная проекция баланса.
        """
        balance.decrease_available_amount(amount_minor)
        return await self.save(balance)

    async def has_sufficient_available_balance(
        self,
        wallet_id: UUID,
        amount_minor: int,
    ) -> bool:
        """Проверяет достаточность доступного баланса.

        Args:
            wallet_id: Идентификатор кошелька.
            amount_minor: Проверяемая сумма.

        Returns:
            True, если средств достаточно.
        """
        return self.balances[wallet_id].has_sufficient_available_balance(amount_minor)

    async def save(self, balance: BalanceProjection) -> BalanceProjection:
        """Сохраняет проекцию баланса.

        Args:
            balance: Обновленная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        self.balances[balance.wallet_id] = balance
        return balance

    async def update(self, balance: BalanceProjection) -> BalanceProjection:
        """Обновляет проекцию баланса.

        Args:
            balance: Обновленная проекция баланса.

        Returns:
            Сохраненная проекция баланса.
        """
        return await self.save(balance)


class InMemoryLedgerTransactionRepository:
    """Хранит ledger transactions в памяти для unit-тестов."""

    def __init__(self) -> None:
        """Создает пустой repository."""
        self.created_transactions: list[LedgerTransaction] = []
        self.transactions_by_operation_id: dict[UUID, LedgerTransaction] = {}

    async def create(self, transaction: LedgerTransaction) -> LedgerTransaction:
        """Сохраняет ledger transaction.

        Args:
            transaction: Доменная ledger transaction.

        Returns:
            Сохраненная ledger transaction.
        """
        self.created_transactions.append(transaction)
        self.transactions_by_operation_id[transaction.operation_id] = transaction
        return transaction

    async def get_by_id(self, transaction_id: UUID) -> LedgerTransaction | None:
        """Возвращает ledger transaction по id.

        Args:
            transaction_id: Идентификатор ledger transaction.

        Returns:
            Ledger transaction или None.
        """
        for transaction in self.transactions_by_operation_id.values():
            if transaction.id == transaction_id:
                return transaction
        return None

    async def get_by_operation_id(
        self,
        operation_id: UUID,
    ) -> LedgerTransaction | None:
        """Возвращает ledger transaction по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            Ledger transaction или None.
        """
        return self.transactions_by_operation_id.get(operation_id)

    async def get_entries_by_wallet_id(self, wallet_id: UUID) -> list[LedgerEntry]:
        """Возвращает ledger entries кошелька.

        Args:
            wallet_id: Идентификатор кошелька.

        Returns:
            Список ledger entries.
        """
        return [
            entry
            for transaction in self.transactions_by_operation_id.values()
            for entry in transaction.entries
            if entry.wallet_id == wallet_id
        ]

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет существование ledger transaction.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если ledger transaction найдена.
        """
        return operation_id in self.transactions_by_operation_id


class FakeTransactionManager:
    """Имитирует transaction manager для unit-тестов."""

    def __init__(self) -> None:
        """Создает fake transaction manager."""
        self.entered = False
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> None:
        """Помечает начало транзакции."""
        self.entered = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Помечает завершение транзакции.

        Args:
            exc_type: Тип исключения, если оно возникло.
            exc: Экземпляр исключения, если оно есть.
            traceback: Traceback исключения, если оно есть.

        Returns:
            None, чтобы не подавлять исключения.
        """
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return None


def make_wallet(*, currency: str = "USD") -> Wallet:
    """Создает кошелек для unit-теста.

    Args:
        currency: Код валюты кошелька.

    Returns:
        Доменный кошелек.
    """
    return Wallet(user_id=uuid4(), currency=currency, status=WalletStatus.ACTIVE)


def make_use_case(
    *,
    source_wallet: Wallet | None = None,
    target_wallet: Wallet | None = None,
    source_balance_amount_minor: int = 500,
    target_balance_amount_minor: int = 20,
) -> tuple[
    InternalDepositUseCase,
    InMemoryLedgerTransactionRepository,
    InMemoryWalletBalanceRepository,
    FakeTransactionManager,
    Wallet,
    Wallet,
]:
    """Создает use case и зависимости для unit-теста.

    Args:
        source_wallet: Funding wallet.
        target_wallet: Target wallet.
        source_balance_amount_minor: Начальный баланс source wallet.
        target_balance_amount_minor: Начальный баланс target wallet.

    Returns:
        Use case, repositories, transaction manager и кошельки.
    """
    resolved_source_wallet = (
        source_wallet if source_wallet is not None else make_wallet()
    )
    resolved_target_wallet = (
        target_wallet if target_wallet is not None else make_wallet()
    )
    balances = InMemoryWalletBalanceRepository(
        [
            BalanceProjection(
                wallet_id=resolved_source_wallet.id,
                currency=resolved_source_wallet.currency,
                available_amount_minor=source_balance_amount_minor,
            ),
            BalanceProjection(
                wallet_id=resolved_target_wallet.id,
                currency=resolved_target_wallet.currency,
                available_amount_minor=target_balance_amount_minor,
            ),
        ]
    )
    ledger_transactions = InMemoryLedgerTransactionRepository()
    transaction_manager = FakeTransactionManager()
    use_case = InternalDepositUseCase(
        wallets=InMemoryWalletRepository(
            [resolved_source_wallet, resolved_target_wallet]
        ),
        balances=balances,
        ledger_transactions=ledger_transactions,
        transaction_manager=transaction_manager,
    )
    return (
        use_case,
        ledger_transactions,
        balances,
        transaction_manager,
        resolved_source_wallet,
        resolved_target_wallet,
    )


async def test_successful_internal_deposit_creates_balanced_ledger_transaction() -> (
    None
):
    """Проверяет создание сбалансированной ledger transaction."""
    (
        use_case,
        ledger_transactions,
        _,
        transaction_manager,
        source_wallet,
        target_wallet,
    ) = make_use_case()
    operation_id = uuid4()

    result = await use_case.execute(
        operation_id=operation_id,
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=100,
        currency="usd",
    )

    transaction = result.transaction
    assert transaction.operation_id == operation_id
    assert transaction.operation_type is LedgerOperationType.INTERNAL_DEPOSIT
    assert transaction.is_balanced()
    assert ledger_transactions.created_transactions == [transaction]
    assert [
        (entry.wallet_id, entry.direction, entry.amount_minor, entry.currency)
        for entry in transaction.entries
    ] == [
        (source_wallet.id, LedgerEntryDirection.DEBIT, 100, "USD"),
        (target_wallet.id, LedgerEntryDirection.CREDIT, 100, "USD"),
    ]
    assert transaction_manager.entered
    assert transaction_manager.committed
    assert not transaction_manager.rolled_back


@pytest.mark.parametrize("amount_minor", [0, -1])
async def test_rejects_non_positive_amount(amount_minor: int) -> None:
    """Проверяет отказ для amount_minor <= 0.

    Args:
        amount_minor: Некорректная сумма операции.
    """
    (
        use_case,
        ledger_transactions,
        _,
        transaction_manager,
        source_wallet,
        target_wallet,
    ) = make_use_case()

    with pytest.raises(InvalidInternalDepositAmountError):
        await use_case.execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=amount_minor,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert not transaction_manager.entered


async def test_rejects_equal_source_and_target_wallets() -> None:
    """Проверяет отказ, если source_wallet_id равен target_wallet_id."""
    use_case, ledger_transactions, _, transaction_manager, source_wallet, _ = (
        make_use_case()
    )

    with pytest.raises(SourceWalletEqualsTargetWalletError):
        await use_case.execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=source_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert not transaction_manager.entered


async def test_rejects_currency_mismatch() -> None:
    """Проверяет отказ при несовпадении валют кошельков."""
    source_wallet = make_wallet(currency="USD")
    target_wallet = make_wallet(currency="EUR")
    use_case, ledger_transactions, _, transaction_manager, _, _ = make_use_case(
        source_wallet=source_wallet,
        target_wallet=target_wallet,
    )

    with pytest.raises(WalletCurrencyMismatchError):
        await use_case.execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert transaction_manager.rolled_back


async def test_rejects_insufficient_source_funds() -> None:
    """Проверяет отказ при недостаточном funding balance."""
    (
        use_case,
        ledger_transactions,
        balances,
        transaction_manager,
        source_wallet,
        target_wallet,
    ) = make_use_case(source_balance_amount_minor=99)

    with pytest.raises(InsufficientSourceFundsError):
        await use_case.execute(
            operation_id=uuid4(),
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == []
    assert balances.balances[source_wallet.id].available_amount_minor == 99
    assert balances.balances[target_wallet.id].available_amount_minor == 20
    assert transaction_manager.rolled_back


async def test_rejects_duplicate_operation_id() -> None:
    """Проверяет отказ для повторного operation_id."""
    (
        use_case,
        ledger_transactions,
        balances,
        transaction_manager,
        source_wallet,
        target_wallet,
    ) = make_use_case()
    operation_id = uuid4()
    first_result = await use_case.execute(
        operation_id=operation_id,
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=100,
        currency="USD",
    )
    transaction_manager.committed = False
    transaction_manager.rolled_back = False

    with pytest.raises(DuplicateInternalDepositOperationError):
        await use_case.execute(
            operation_id=operation_id,
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            amount_minor=100,
            currency="USD",
        )

    assert ledger_transactions.created_transactions == [first_result.transaction]
    assert balances.balances[source_wallet.id].available_amount_minor == 400
    assert balances.balances[target_wallet.id].available_amount_minor == 120
    assert transaction_manager.rolled_back


async def test_successful_internal_deposit_updates_balances() -> None:
    """Проверяет уменьшение source balance и увеличение target balance."""
    use_case, _, balances, _, source_wallet, target_wallet = make_use_case(
        source_balance_amount_minor=500,
        target_balance_amount_minor=20,
    )

    result = await use_case.execute(
        operation_id=uuid4(),
        source_wallet_id=source_wallet.id,
        target_wallet_id=target_wallet.id,
        amount_minor=125,
        currency="USD",
    )

    assert result.source_balance.available_amount_minor == 375
    assert result.target_balance.available_amount_minor == 145
    assert balances.balances[source_wallet.id].available_amount_minor == 375
    assert balances.balances[target_wallet.id].available_amount_minor == 145
