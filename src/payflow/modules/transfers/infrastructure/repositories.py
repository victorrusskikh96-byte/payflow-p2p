"""SQLAlchemy-репозиторий пользовательских P2P-переводов."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.transfers.application.repositories import TransferRepository
from payflow.modules.transfers.domain import Transfer, TransferNotFoundError
from payflow.modules.transfers.infrastructure.mappers import (
    transfer_entity_to_model,
    transfer_model_to_entity,
)
from payflow.modules.transfers.infrastructure.models import TransferModel


class SQLAlchemyTransferRepository(TransferRepository):
    """Работает с P2P-переводами через асинхронную SQLAlchemy-сессию."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает репозиторий P2P-переводов.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session

    async def create(self, transfer: Transfer) -> Transfer:
        """Сохраняет новый P2P-перевод в базе данных.

        Args:
            transfer: Доменная сущность перевода.

        Returns:
            Сохраненный P2P-перевод.

        Raises:
            sqlalchemy.exc.IntegrityError: Если база данных отклоняет ограничения.
        """
        transfer_model = transfer_entity_to_model(transfer)
        self._session.add(transfer_model)
        await self._session.flush()
        return transfer_model_to_entity(transfer_model)

    async def get_by_id(self, transfer_id: UUID) -> Transfer | None:
        """Возвращает P2P-перевод по идентификатору.

        Args:
            transfer_id: Идентификатор перевода.

        Returns:
            P2P-перевод или None, если запись не найдена.
        """
        transfer_model = await self._session.get(TransferModel, transfer_id)
        if transfer_model is None:
            return None
        return transfer_model_to_entity(transfer_model)

    async def get_by_operation_id(self, operation_id: UUID) -> Transfer | None:
        """Возвращает P2P-перевод по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            P2P-перевод или None, если запись не найдена.
        """
        statement = select(TransferModel).where(
            TransferModel.operation_id == operation_id,
        )
        transfer_model = await self._session.scalar(statement)
        if transfer_model is None:
            return None
        return transfer_model_to_entity(transfer_model)

    async def get_by_sender_user_id(self, sender_user_id: UUID) -> list[Transfer]:
        """Возвращает P2P-переводы отправителя.

        Args:
            sender_user_id: Идентификатор пользователя-отправителя.

        Returns:
            Список P2P-переводов отправителя.
        """
        statement = (
            select(TransferModel)
            .where(TransferModel.sender_user_id == sender_user_id)
            .order_by(TransferModel.created_at, TransferModel.id)
        )
        result = await self._session.scalars(statement)
        return [
            transfer_model_to_entity(transfer_model) for transfer_model in result.all()
        ]

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет наличие P2P-перевода по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если P2P-перевод найден.
        """
        statement = select(exists().where(TransferModel.operation_id == operation_id))
        return bool(await self._session.scalar(statement))

    async def save_status(self, transfer: Transfer) -> Transfer:
        """Сохраняет статус и ledger transaction id P2P-перевода.

        Args:
            transfer: Доменная сущность перевода с обновленным статусом.

        Returns:
            Обновленный P2P-перевод.

        Raises:
            TransferNotFoundError: Если запись перевода не найдена.
        """
        transfer_model = await self._session.get(TransferModel, transfer.id)
        if transfer_model is None:
            raise TransferNotFoundError("Transfer was not found.")

        transfer_model.status = transfer.status.value
        transfer_model.ledger_transaction_id = transfer.ledger_transaction_id
        transfer_model.updated_at = transfer.updated_at
        transfer_model.failed_at = transfer.failed_at

        await self._session.flush()
        return transfer_model_to_entity(transfer_model)
