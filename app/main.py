from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, jobs, worker
from app.core.config import get_settings
from app.core.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()

    application = FastAPI(title=settings.app_name)
    allowed_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
    if not allowed_origins:
        allowed_origins = ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
