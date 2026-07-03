"""Интерфейс менеджера транзакций для application-слоя."""

from types import TracebackType
from typing import Protocol


class TransactionManager(Protocol):
    """Описывает контракт асинхронного управления транзакцией."""

    async def __aenter__(self) -> None:
        """Начинает транзакцию базы данных."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Завершает транзакцию с commit или rollback.

        Args:
            exc_type: Тип исключения, если оно возникло в транзакции.
            exc: Экземпляр исключения, если он есть.
            traceback: Traceback исключения, если он есть.

        Returns:
            True, если исключение подавлено; иначе None или False.
        """
