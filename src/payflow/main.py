from fastapi import FastAPI

from payflow.api.router import router
from payflow.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(router)
    return app


app = create_app()
