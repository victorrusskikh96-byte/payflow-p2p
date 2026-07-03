"""SQLAlchemy-реализация менеджера транзакций."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction


class SQLAlchemyTransactionManager:
    """Управляет жизненным циклом транзакции SQLAlchemy-сессии."""

    def __init__(self, session: AsyncSession) -> None:
        """Создает менеджер транзакций.

        Args:
            session: Асинхронная SQLAlchemy-сессия.
        """
        self._session = session
        self._transaction: AsyncSessionTransaction | None = None

    async def __aenter__(self) -> None:
        """Открывает транзакцию базы данных."""
        self._transaction = self._session.begin()
        await self._transaction.__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Завершает транзакцию и очищает внутреннее состояние.

        Args:
            exc_type: Тип исключения, если оно возникло в транзакции.
            exc: Экземпляр исключения, если он есть.
            traceback: Traceback исключения, если он есть.

        Returns:
            None, чтобы не подавлять исключения.

        Raises:
            RuntimeError: Если транзакция не была открыта.
        """
        if self._transaction is None:
            raise RuntimeError("Transaction was not started.")

        try:
            await self._transaction.__aexit__(exc_type, exc, traceback)
            return None
        finally:
            self._transaction = None
