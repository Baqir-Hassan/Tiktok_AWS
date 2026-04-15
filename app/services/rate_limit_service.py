from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job
from app.models.user import User


settings = get_settings()


class RateLimitService:
    def __init__(self, db: Session):
        self.db = db

    def enforce_job_creation_limit(self, user: User) -> None:
        window_start = datetime.now(timezone.utc) - timedelta(seconds=settings.job_rate_limit_window_seconds)
        recent_jobs = self.db.scalar(
            select(func.count(Job.id)).where(Job.user_id == user.id, Job.created_at >= window_start)
        )
        if recent_jobs >= settings.job_rate_limit_count:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for job creation",
            )
