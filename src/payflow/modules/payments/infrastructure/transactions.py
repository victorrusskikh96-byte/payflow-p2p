"""SQLAlchemy-реализация менеджера транзакций для payments module."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction


class SQLAlchemyTransactionManager:
    """Управляет транзакцией SQLAlchemy-сессии для payments use cases."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает менеджер транзакций.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session
        self._transaction: AsyncSessionTransaction | None = None
        self._started_transaction = False

    async def __aenter__(self) -> None:
        """Открывает транзакцию базы данных или переиспользует активную."""
        if self._session.in_transaction():
            self._started_transaction = False
            return

        self._transaction = self._session.begin()
        self._started_transaction = True
        await self._transaction.__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Завершает транзакцию commit или rollback.

        Args:
            exc_type: Тип исключения, если оно возникло в транзакции.
            exc: Экземпляр исключения, если оно есть.
            traceback: Traceback исключения, если оно есть.

        Returns:
            None, чтобы не подавлять исключения.
        """
        if not self._started_transaction:
            return None

        try:
            if self._transaction is not None:
                await self._transaction.__aexit__(exc_type, exc, traceback)
        finally:
            self._transaction = None
            self._started_transaction = False

        return None
