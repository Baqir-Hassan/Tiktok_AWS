from fastapi import APIRouter

from app.api.routes import admin, auth, jobs, worker


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(worker.router)
api_router.include_router(jobs.router)
api_router.include_router(admin.router)
