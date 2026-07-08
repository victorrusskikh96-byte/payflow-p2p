"""Dev-only CLI-команда для локального internal deposit через Financial Core."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payflow.core.config import settings
from payflow.core.database import async_session_factory
from payflow.modules.financial_core.application.payments.use_cases import (
    InternalDepositUseCase,
)
from payflow.modules.financial_core.domain.wallets import (
    BalanceProjection,
    Wallet,
    normalize_currency,
)
from payflow.modules.financial_core.infrastructure.repositories.ledger import (
    SQLAlchemyLedgerTransactionRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.outbox import (
    SQLAlchemyOutboxEventRepository,
)
from payflow.modules.financial_core.infrastructure.repositories.wallets import (
    SQLAlchemyWalletBalanceRepository,
    SQLAlchemyWalletRepository,
)
from payflow.modules.financial_core.infrastructure.transactions import (
    SQLAlchemyTransactionManager,
)
from payflow.modules.users.domain import User
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository

DEV_ONLY_ALLOWED_ENVS = frozenset({"local", "dev", "development", "test", "testing"})
DEV_FUNDING_USER_EMAIL = "dev-internal-deposit-source@payflow.local"
DEV_FUNDING_INITIAL_BALANCE_MINOR = 9_000_000_000_000_000_000


class DevInternalDepositError(Exception):
    """Базовая ошибка dev-only команды internal deposit."""


class DevInternalDepositEnvironmentError(DevInternalDepositError):
    """Сообщает, что команда запущена не в local/dev/test окружении."""


class DevInternalDepositInputError(DevInternalDepositError):
    """Сообщает, что входные параметры dev-only команды некорректны."""


@dataclass(frozen=True, slots=True)
class DevInternalDepositResult:
    """Хранит результат выполнения dev-only internal deposit команды."""

    operation_id: UUID
    wallet_id: UUID
    amount_minor: int
    currency: str
    ledger_transaction_id: UUID


def build_arg_parser() -> argparse.ArgumentParser:
    """Создает parser аргументов dev-only команды.

    Returns:
        Настроенный parser аргументов CLI.
    """
    parser = argparse.ArgumentParser(
        description=(
            "DEV-ONLY: выполнить internal deposit через Financial Core use case."
        ),
    )
    parser.add_argument("--wallet-id", required=True, help="Target wallet UUID.")
    parser.add_argument(
        "--amount-minor",
        required=True,
        type=int,
        help="Сумма пополнения в минорных единицах.",
    )
    parser.add_argument("--currency", required=True, help="Код валюты, например RUB.")
    parser.add_argument(
        "--operation-id",
        required=False,
        help=(
            "Идемпотентный UUID операции. Если не передан, генерируется автоматически."
        ),
    )
    return parser


async def run_internal_deposit(
    *,
    wallet_id: UUID | str,
    amount_minor: int,
    currency: str,
    operation_id: UUID | str | None = None,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    app_env: str | None = None,
) -> DevInternalDepositResult:
    """Выполняет dev-only internal deposit через application flow Financial Core.

    Args:
        wallet_id: Идентификатор target wallet.
        amount_minor: Сумма пополнения в минорных единицах.
        currency: Валюта операции.
        operation_id: Идентификатор операции или None для автогенерации.
        session_factory: Фабрика SQLAlchemy-сессий.
        app_env: Явное окружение для проверки dev-only режима.

    Returns:
        Результат успешного dev-only internal deposit.

    Raises:
        DevInternalDepositEnvironmentError: Если окружение не local/dev/test.
        DevInternalDepositInputError: Если входные параметры некорректны.
        PaymentsApplicationError: Если `InternalDepositUseCase` отклонил операцию.
        WalletNotFoundError: Если target wallet не найден.
    """
    _ensure_dev_environment(app_env=app_env)
    target_wallet_id = _parse_uuid(wallet_id, parameter_name="wallet_id")
    resolved_operation_id = (
        _parse_uuid(operation_id, parameter_name="operation_id")
        if operation_id is not None
        else uuid4()
    )
    if amount_minor <= 0:
        raise DevInternalDepositInputError("amount_minor must be positive.")
    normalized_currency = normalize_currency(currency)

    async with session_factory() as session:
        source_wallet = await _get_or_create_dev_funding_wallet(
            session,
            currency=normalized_currency,
        )
        use_case = _build_internal_deposit_use_case(session)
        result = await use_case.execute(
            operation_id=resolved_operation_id,
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet_id,
            amount_minor=amount_minor,
            currency=normalized_currency,
        )

    return DevInternalDepositResult(
        operation_id=resolved_operation_id,
        wallet_id=target_wallet_id,
        amount_minor=amount_minor,
        currency=normalized_currency,
        ledger_transaction_id=result.transaction.id,
    )


def format_success_message(result: DevInternalDepositResult) -> str:
    """Форматирует понятный результат успешного dev-only deposit.

    Args:
        result: Результат команды internal deposit.

    Returns:
        Многострочное сообщение для CLI.
    """
    return "\n".join(
        (
            "DEV-ONLY internal deposit completed successfully.",
            f"operation_id: {result.operation_id}",
            f"wallet_id: {result.wallet_id}",
            f"amount_minor: {result.amount_minor}",
            f"currency: {result.currency}",
            f"ledger_transaction_id: {result.ledger_transaction_id}",
            "status: success",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Запускает dev-only internal deposit CLI.

    Args:
        argv: Аргументы командной строки без имени процесса.

    Returns:
        Код завершения процесса.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        result = asyncio.run(
            run_internal_deposit(
                wallet_id=args.wallet_id,
                amount_minor=args.amount_minor,
                currency=args.currency,
                operation_id=args.operation_id,
            )
        )
    except Exception as exc:
        print(f"DEV-ONLY internal deposit failed: {exc}", file=sys.stderr)
        return 1

    print(format_success_message(result))
    return 0


def _ensure_dev_environment(*, app_env: str | None) -> None:
    configured_values = [
        value
        for value in (
            app_env if app_env is not None else settings.app_env,
            None if app_env is not None else os.getenv("ENVIRONMENT"),
        )
        if value is not None and value.strip()
    ]
    normalized_values = {value.strip().lower() for value in configured_values}
    if not normalized_values:
        raise DevInternalDepositEnvironmentError(
            "APP_ENV or ENVIRONMENT must point to local/dev/test."
        )
    disallowed_values = normalized_values - DEV_ONLY_ALLOWED_ENVS
    if disallowed_values:
        raise DevInternalDepositEnvironmentError(
            "dev internal deposit is disabled outside local/dev/test environments."
        )


def _parse_uuid(value: UUID | str, *, parameter_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except ValueError as exc:
        raise DevInternalDepositInputError(
            f"{parameter_name} must be a valid UUID."
        ) from exc


async def _get_or_create_dev_funding_wallet(
    session: AsyncSession,
    *,
    currency: str,
) -> Wallet:
    users = SQLAlchemyUserRepository(session)
    wallets = SQLAlchemyWalletRepository(session)
    balances = SQLAlchemyWalletBalanceRepository(session)

    user = await users.get_by_email(DEV_FUNDING_USER_EMAIL)
    if user is None:
        user = await users.create(User(email=DEV_FUNDING_USER_EMAIL))

    wallet = await wallets.get_by_user_id_and_currency(user.id, currency)
    if wallet is None:
        wallet = await wallets.create(Wallet(user_id=user.id, currency=currency))

    balance = await balances.get_by_wallet_id(wallet.id)
    if balance is None:
        await balances.create_initial(
            BalanceProjection(
                wallet_id=wallet.id,
                currency=currency,
                available_amount_minor=DEV_FUNDING_INITIAL_BALANCE_MINOR,
            )
        )

    return wallet


def _build_internal_deposit_use_case(session: AsyncSession) -> InternalDepositUseCase:
    return InternalDepositUseCase(
        wallets=SQLAlchemyWalletRepository(session),
        balances=SQLAlchemyWalletBalanceRepository(session),
        ledger_transactions=SQLAlchemyLedgerTransactionRepository(session),
        outbox_events=SQLAlchemyOutboxEventRepository(session),
        transaction_manager=SQLAlchemyTransactionManager(session),
    )


if __name__ == "__main__":
    raise SystemExit(main())
