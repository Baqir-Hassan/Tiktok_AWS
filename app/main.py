from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, jobs, worker
from app.core.config import get_settings
from app.core.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()

    application = FastAPI(title=settings.app_name)
    application.include_router(auth.router)
    application.include_router(worker.router)
    application.include_router(jobs.router)

    if settings.storage_backend.lower() == "local":
        application.mount("/media", StaticFiles(directory=str(settings.local_storage_path)), name="media")

    @application.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
