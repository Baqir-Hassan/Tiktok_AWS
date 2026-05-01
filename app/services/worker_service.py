from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.job import Job, JobStatus
from app.models.job_log import JobLog
from app.schemas.worker import WorkerJobStage


LEGACY_PROCESSING_STATUSES = {
    JobStatus.SCRAPING.value,
    JobStatus.GENERATING_SCRIPT.value,
    JobStatus.GENERATING_TTS.value,
    JobStatus.GENERATING_SUBTITLES.value,
    JobStatus.RENDERING_VIDEO.value,
}
ACTIVE_PROCESSING_STATUSES = {JobStatus.PROCESSING.value, *LEGACY_PROCESSING_STATUSES}


class WorkerService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def get_next_job(self) -> Job | None:
        self.requeue_stale_jobs()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        job = self.db.scalar(
            select(Job)
            .where(Job.status == JobStatus.QUEUED.value)
            .where(or_(Job.lease_expires_at.is_(None), Job.lease_expires_at < now))
            .order_by(Job.created_at.asc())
        )
        if not job:
            return None

        # Used by workers to avoid selecting duplicate Reddit stories for a user.
        job.excluded_reddit_post_ids = self._get_user_used_post_ids(job.user_id, job.subreddit)
        return job

    def claim_job(self, job_id: int, worker_id: str) -> Job:
        now = datetime.now(timezone.utc)
        # SQLite stores datetimes without timezone; use naive for DB operations
        now_naive = now.replace(tzinfo=None)
        lease_expires_at = self._next_lease_expiration(now)
        result = self.db.execute(
            update(Job)
            .where(Job.id == job_id)
            .where(Job.status == JobStatus.QUEUED.value)
            .where(or_(Job.lease_expires_at.is_(None), Job.lease_expires_at < now_naive))
            .values(
                status=JobStatus.PROCESSING.value,
                progress=10,
                attempts=Job.attempts + 1,
                claimed_by=worker_id,
                claimed_at=now_naive,
                lease_expires_at=lease_expires_at,
                started_at=func.coalesce(Job.started_at, now_naive),
                error_message=None,
            )
        )
        if result.rowcount:
            self.db.add(
                JobLog(
                    job_id=job_id,
                    stage=WorkerJobStage.SCRAPING.value,
                    message=f"Job claimed by worker {worker_id}",
                )
            )
            self.db.commit()
            return self._get_job(job_id)

        job = self._get_job(job_id)
        if job.claimed_by == worker_id and self._is_processing_status(job.status) and self._is_lease_active(job):
            return job
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is no longer claimable")

    def update_job(
        self,
        job_id: int,
        next_stage: WorkerJobStage,
        worker_id: str,
        message: str,
        progress: int | None = None,
        source_title: str | None = None,
        source_post_id: str | None = None,
        source_permalink: str | None = None,
        script: str | None = None,
    ) -> Job:
        job = self._get_job(job_id)
        self._ensure_processing_mutation_allowed(job, worker_id)

        job.status = JobStatus.PROCESSING.value
        job.lease_expires_at = self._next_lease_expiration(datetime.now(timezone.utc))
        if progress is not None:
            job.progress = progress
        if source_title is not None:
            job.source_title = source_title
        if source_post_id is not None:
            job.source_post_id = source_post_id
        if source_permalink is not None:
            job.source_permalink = source_permalink
        if script is not None:
            job.script = script

        self.db.add(job)
        self.db.add(JobLog(job_id=job.id, stage=next_stage.value, message=message))
        self.db.commit()
        self.db.refresh(job)
        return job

    def complete_job(self, job_id: int, worker_id: str, video_url: str, message: str) -> Job:
        job = self._get_job(job_id)
        if job.status == JobStatus.COMPLETED.value:
            return job

        self._ensure_processing_mutation_allowed(job, worker_id)
        if job.uploaded_video_url and job.uploaded_video_url != video_url:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job already has a different uploaded video recorded",
            )

        if job.video_upload_status == "pending":
            job.uploaded_video_url = video_url
            job.video_upload_status = "uploaded"
            job.lease_expires_at = self._next_lease_expiration(datetime.now(timezone.utc))
            self.db.add(job)
            self.db.add(
                JobLog(
                    job_id=job.id,
                    stage=JobStatus.PROCESSING.value,
                    message=f"Uploaded video registered at {video_url}",
                )
            )
            self.db.commit()
            self.db.refresh(job)
            self._ensure_processing_mutation_allowed(job, worker_id)

        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.video_url = job.uploaded_video_url or video_url
        job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.lease_expires_at = None
        job.video_upload_status = "completed"
        job.error_message = None

        self.db.add(job)
        self.db.add(JobLog(job_id=job.id, stage=JobStatus.COMPLETED.value, message=message))
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail_job(self, job_id: int, worker_id: str, error_message: str, message: str) -> Job:
        job = self._get_job(job_id)
        if job.status == JobStatus.COMPLETED.value:
            return job
        if job.status == JobStatus.FAILED.value:
            return job
        if job.video_upload_status in {"uploaded", "completed"} or job.uploaded_video_url:
            return job

        self._ensure_processing_mutation_allowed(job, worker_id)

        # Refund the credit since the job didn't produce a video
        if job.user and job.user.credits < 1000:  # safety cap
            job.user.credits += self.settings.job_cost_credits
            self.db.add(job.user)

        job.status = JobStatus.FAILED.value
        job.progress = 100
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.lease_expires_at = None

        self.db.add(job)
        self.db.add(JobLog(job_id=job.id, stage=JobStatus.FAILED.value, message=message))
        self.db.commit()
        self.db.refresh(job)
        return job

    def heartbeat_job(self, job_id: int, worker_id: str) -> Job:
        job = self._get_job(job_id)
        self._ensure_worker_owns_job(job, worker_id)
        if not self._is_processing_status(job.status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot heartbeat job in status {job.status}",
            )

        job.heartbeat_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def requeue_stale_jobs(self) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stale_jobs = list(
            self.db.execute(
                update(Job)
                .where(Job.status.in_(tuple(ACTIVE_PROCESSING_STATUSES)))
                .where(Job.lease_expires_at.is_not(None))
                .where(Job.lease_expires_at <= now)
                .values(
                    status=JobStatus.QUEUED.value,
                    progress=0,
                    claimed_by=None,
                    claimed_at=None,
                    heartbeat_at=None,
                    lease_expires_at=None,
                )
                .returning(Job.id, Job.claimed_by)
            )
        )

        for stale_job_id, _ in stale_jobs:
            self.db.add(
                JobLog(
                    job_id=stale_job_id,
                    stage=JobStatus.QUEUED.value,
                    message="Job re-queued after lease expiry",
                )
            )

        if stale_jobs:
            self.db.commit()

        return len(stale_jobs)

    def _get_job(self, job_id: int) -> Job:
        job = self.db.get(Job, job_id, options=[joinedload(Job.user)])
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    def _ensure_processing_mutation_allowed(self, job: Job, worker_id: str) -> None:
        if not self._is_processing_status(job.status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid job state transition: {job.status} -> mutation not allowed",
            )
        self._ensure_worker_owns_job(job, worker_id)

    def _ensure_worker_owns_job(self, job: Job, worker_id: str) -> None:
        if not self._is_lease_active(job):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job lease has expired",
            )
        if job.claimed_by != worker_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job is not currently claimed by this worker",
            )

    def _is_lease_active(self, job: Job) -> bool:
        if not job.lease_expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires = job.lease_expires_at
        # SQLite stores datetimes without timezone; make naive if needed for comparison
        if expires.tzinfo is None:
            now = now.replace(tzinfo=None)
        return expires > now

    def _is_processing_status(self, job_status: str) -> bool:
        return job_status in ACTIVE_PROCESSING_STATUSES

    def _next_lease_expiration(self, now: datetime) -> datetime:
        expires = now + timedelta(minutes=self.settings.worker_stale_timeout_minutes)
        # SQLite stores datetimes without timezone; strip tzinfo for consistent storage
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
        return expires

    def _get_user_used_post_ids(self, user_id: int, subreddit: str, limit: int = 500) -> list[str]:
        rows = self.db.scalars(
            select(Job.source_post_id)
            .where(Job.user_id == user_id)
            .where(Job.subreddit == subreddit)
            .where(Job.source_post_id.is_not(None))
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        seen: set[str] = set()
        result: list[str] = []
        for value in rows:
            if not value:
                continue
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
