"""HTTP-маршруты верхнего уровня для приложения Payflow."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from payflow.modules.auth.api.router import router as auth_router
from payflow.modules.financial_core.api.transfers import router as transfers_router
from payflow.modules.financial_core.api.wallets import router as wallets_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(transfers_router, prefix="/transfers", tags=["transfers"])
router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])


class HealthResponse(BaseModel):
    """Описывает ответ health endpoint приложения."""

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})

    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=200,
    summary="Проверить состояние приложения",
    description="Возвращает простой статус доступности основного HTTP API.",
    operation_id="health_check",
)
async def health_check() -> HealthResponse:
    """Возвращает состояние доступности приложения.

    Returns:
        Текущий статус сервиса.
    """
    return HealthResponse(status="ok")
