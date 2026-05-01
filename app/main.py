from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.services.readiness_service import collect_readiness_status


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
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", tags=["health"])
    def readiness_check() -> JSONResponse:
        readiness = collect_readiness_status(include_details=not settings.is_production)
        status_code = 200 if readiness["status"] == "ready" else 503
        return JSONResponse(status_code=status_code, content=readiness)

    return application


app = create_app()
