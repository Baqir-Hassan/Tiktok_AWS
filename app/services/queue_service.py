from __future__ import annotations

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.job import Job


def check_queue_connection() -> dict[str, object]:
    settings = get_settings()
    provider = settings.queue_provider.strip().lower()

    if provider != "database":
        return {
            "provider": provider,
            "ready": False,
            "detail": f"Unsupported queue provider: {settings.queue_provider}",
        }

    try:
        with SessionLocal() as db:
            queued_jobs = db.scalar(select(func.count()).select_from(Job))
        return {
            "provider": "database",
            "ready": True,
            "job_count": int(queued_jobs or 0),
        }
    except Exception as exc:
        return {"provider": "database", "ready": False, "detail": str(exc)}
