"""HTTP-маршруты верхнего уровня для приложения Payflow."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Возвращает состояние доступности приложения.

    Returns:
        Словарь с текущим статусом сервиса.
    """
    return {"status": "ok"}
