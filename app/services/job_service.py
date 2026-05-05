import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.job import Job, JobStatus
from app.models.job_log import JobLog
from app.models.user import User
from app.services.rate_limit_service import RateLimitService

logger = logging.getLogger(__name__)


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
            custom_story_title=custom_title,
            custom_story=custom_story,
        )
        user.credits -= settings.job_cost_credits
        self.db.add(job)
        self.db.add(JobLog(job=job, stage=JobStatus.QUEUED.value, message="Job created and queued"))
        self.db.commit()
        self.db.refresh(job)
        
        # Trigger Modal worker
        self._trigger_modal_worker(job)
        
        return job

    def _trigger_modal_worker(self, job: Job) -> None:
        """Trigger the Modal worker function for the job."""
        try:
            import modal
            from app.services.worker_service import WorkerService

            process_job_fn = modal.Function.from_name("saas-worker", "process_job")
            
            worker_service = WorkerService(self.db)
            excluded_ids = worker_service._get_user_used_post_ids(job.user_id, job.subreddit)

            job_dict = {
                "id": job.id,
                "user_id": job.user_id,
                "status": job.status,
                "subreddit": job.subreddit,
                "script": job.script,
                "tts_provider": job.tts_provider,
                "source_title": job.source_title,
                "source_text": job.source_text,
                "source_post_id": job.source_post_id,
                "source_permalink": job.source_permalink,
                "excluded_reddit_post_ids": excluded_ids,
                "video_url": job.video_url,
                "uploaded_video_url": job.uploaded_video_url,
                "video_upload_status": job.video_upload_status,
                "error_message": job.error_message,
                "progress": job.progress,
                "attempts": job.attempts,
                "claimed_by": job.claimed_by,
                "claimed_at": job.claimed_at.isoformat() if job.claimed_at else None,
                "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
                "lease_expires_at": job.lease_expires_at.isoformat() if job.lease_expires_at else None,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "custom_story": job.custom_story,
                "custom_story_title": job.custom_story_title,
            }

            process_job_fn.spawn(job_dict)

        except Exception as e:
            logger.exception("Failed to trigger Modal worker for job %s", job.id)
            try:
                self.db.add(JobLog(job_id=job.id, stage=JobStatus.QUEUED.value, message=f"Modal trigger failed: {e}"))
                self.db.commit()
            except Exception:
                logger.exception("Failed to log Modal trigger failure for job %s", job.id)

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
            job.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if status_value in {JobStatus.COMPLETED, JobStatus.FAILED}:
            job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(job)
        if message:
            self.db.add(JobLog(job_id=job.id, stage=status_value.value, message=message))
        self.db.commit()
        self.db.refresh(job)
        return job
