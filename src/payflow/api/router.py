"""HTTP-маршруты верхнего уровня для приложения Payflow."""

from fastapi import APIRouter

from payflow.modules.auth.api.router import router as auth_router
from payflow.modules.financial_core.api.transfers import router as transfers_router
from payflow.modules.financial_core.api.wallets import router as wallets_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(transfers_router, prefix="/transfers", tags=["transfers"])
router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Возвращает состояние доступности приложения.

    Returns:
        Словарь с текущим статусом сервиса.
    """
    return {"status": "ok"}
