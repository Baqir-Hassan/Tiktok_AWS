from datetime import datetime, timezone
from time import sleep

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_log import JobLog
from app.pipelines.video_pipeline import VideoGenerationPipeline


class JobRunner:
    def __init__(self) -> None:
        self.settings = get_settings()

    def start(self) -> None:
        while True:
            if not self.process_next_job():
                sleep(self.settings.worker_poll_interval_seconds)

    def process_next_job(self) -> bool:
        with SessionLocal() as db:
            job = self._claim_next_job(db)
            if not job:
                return False

            pipeline = VideoGenerationPipeline(db)
            try:
                pipeline.run(job)
            except Exception as exc:
                db.refresh(job)
                if job.attempts < self.settings.max_job_retries:
                    job.status = JobStatus.QUEUED.value
                    retry_message = f"Attempt failed, retrying: {exc}"
                else:
                    job.status = JobStatus.FAILED.value
                    job.completed_at = datetime.now(timezone.utc)
                    retry_message = f"Job failed permanently: {exc}"
                job.error_message = str(exc)
                db.add(job)
                db.add(JobLog(job_id=job.id, stage=JobStatus.FAILED.value, message=retry_message))
                db.commit()
            return True

    def _claim_next_job(self, db: Session) -> Job | None:
        statement = select(Job).where(Job.status == JobStatus.QUEUED.value).order_by(Job.created_at.asc())
        if db.get_bind().dialect.name != "sqlite":
            statement = statement.with_for_update(skip_locked=True)
        job = db.scalar(statement)
        if not job:
            return None

        job.status = JobStatus.SCRAPING.value
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        db.add(job)
        db.add(JobLog(job_id=job.id, stage=JobStatus.SCRAPING.value, message="Job claimed by worker"))
        db.commit()
        db.refresh(job)
        return job
