from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.job import Job, JobStatus
from app.models.job_log import JobLog
from app.models.user import User
from app.services.rate_limit_service import RateLimitService


settings = get_settings()


class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.rate_limiter = RateLimitService(db)

    def create_job(self, user: User, subreddit: str, tts_provider: str, custom_title: str | None = None, custom_story: str | None = None) -> Job:
        self.rate_limiter.enforce_job_creation_limit(user)
        if user.credits < settings.job_cost_credits:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")
        job = Job(
            user_id=user.id,
            status=JobStatus.QUEUED.value,
            subreddit=subreddit or "custom",
            tts_provider=tts_provider,
            video_upload_status="pending",
            source_title=custom_title,
            source_text=custom_story,
        )
        user.credits -= settings.job_cost_credits
        self.db.add(job)
        self.db.add(JobLog(job=job, stage=JobStatus.QUEUED.value, message="Job created and queued"))
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, user: User) -> list[Job]:
        return list(
            self.db.scalars(
                select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())
            )
        )

    def get_job_for_user(self, user: User, job_id: int) -> Job:
        job = self.db.scalar(
            select(Job)
            .options(selectinload(Job.logs))
            .where(Job.id == job_id, Job.user_id == user.id)
        )
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    def update_status(self, job: Job, status_value: JobStatus, message: str | None = None) -> Job:
        job.status = status_value.value
        if status_value == JobStatus.SCRAPING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        if status_value in {JobStatus.COMPLETED, JobStatus.FAILED}:
            job.completed_at = datetime.now(timezone.utc)
        self.db.add(job)
        if message:
            self.db.add(JobLog(job_id=job.id, stage=status_value.value, message=message))
        self.db.commit()
        self.db.refresh(job)
        return job
