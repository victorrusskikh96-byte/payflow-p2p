"""Интерфейсы репозиториев для P2P-переводов."""

from typing import Protocol
from uuid import UUID

from payflow.modules.transfers.domain import Transfer


class TransferRepository(Protocol):
    """Определяет контракт хранилища P2P-переводов для application layer."""

    async def create(self, transfer: Transfer) -> Transfer:
        """Сохраняет новый P2P-перевод.

        Args:
            transfer: Доменная сущность перевода.

        Returns:
            Сохраненный перевод.
        """

    async def get_by_id(self, transfer_id: UUID) -> Transfer | None:
        """Возвращает P2P-перевод по идентификатору.

        Args:
            transfer_id: Идентификатор перевода.

        Returns:
            P2P-перевод или None, если запись не найдена.
        """

    async def get_by_operation_id(self, operation_id: UUID) -> Transfer | None:
        """Возвращает P2P-перевод по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            P2P-перевод или None, если запись не найдена.
        """

    async def get_by_sender_user_id(self, sender_user_id: UUID) -> list[Transfer]:
        """Возвращает P2P-переводы отправителя.

        Args:
            sender_user_id: Идентификатор пользователя-отправителя.

        Returns:
            Список P2P-переводов отправителя.
        """

    async def exists_by_operation_id(self, operation_id: UUID) -> bool:
        """Проверяет существование P2P-перевода по operation_id.

        Args:
            operation_id: Идентификатор бизнес-операции.

        Returns:
            True, если P2P-перевод найден.
        """

    async def save_status(self, transfer: Transfer) -> Transfer:
        """Сохраняет статус и ledger transaction id P2P-перевода.

        Args:
            transfer: Доменная сущность перевода с обновленным статусом.

        Returns:
            Обновленный P2P-перевод.

        Raises:
            TransferNotFoundError: Если перевод не найден.
        """
