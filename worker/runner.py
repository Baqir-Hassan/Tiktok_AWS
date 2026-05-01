import logging
import time

from worker.api_client import WorkerApiClient, WorkerStopError
from worker.config import WorkerSettings
from worker.pipeline import WorkerPipeline


LOGGER = logging.getLogger(__name__)


class WorkerRunner:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings
        self.api_client = WorkerApiClient(settings)
        self.pipeline = WorkerPipeline(settings, self.api_client)

    def _get_user_friendly_error_message(self, exc: Exception) -> str:
        """Convert technical exceptions to user-friendly messages."""
        error_msg = str(exc).lower()

        # Reddit/Network related errors
        if "reddit" in error_msg or "network" in error_msg or "connection" in error_msg:
            return "Failed to fetch content from Reddit. Please try again or use a different subreddit."

        # API/Rate limit errors
        if "rate limit" in error_msg or "429" in error_msg:
            return "Reddit API rate limit exceeded. Please try again in a few minutes."

        # TTS/Script generation errors
        if "groq" in error_msg or "api" in error_msg or "key" in error_msg:
            return "Failed to generate script or audio. Please check your API configuration."

        # Video rendering errors
        if "ffmpeg" in error_msg or "render" in error_msg or "memory" in error_msg:
            return "Video processing failed. This might be due to memory issues. Please try a shorter post."

        # Storage/S3 errors
        if "s3" in error_msg or "upload" in error_msg or "storage" in error_msg:
            return "Failed to upload video. Please check your storage settings."

        # Default fallback
        return "Video processing failed due to an unexpected error. Our team has been notified and will look into it."

    def run_forever(self) -> None:
        LOGGER.info("Worker %s started", self.settings.worker_id)
        while True:
            try:
                job = self.api_client.get_next_job()
                if not job:
                    time.sleep(self.settings.poll_interval_seconds)
                    continue

                LOGGER.info("Discovered queued job %s", job.id)
                self.api_client.claim_job(job.id)

                try:
                    self.pipeline.run(job)
                except Exception as exc:
                    LOGGER.exception("Job %s failed", job.id)
                    # Map technical errors to user-friendly messages
                    user_friendly_message = self._get_user_friendly_error_message(exc)
                    try:
                        self.api_client.fail_job(job.id, str(exc), user_friendly_message)
                    except Exception as stop_exc:
                        LOGGER.warning("Job %s fail request aborted: %s", job.id, stop_exc)
            except Exception:
                LOGGER.exception("Worker loop iteration failed")
                time.sleep(self.settings.poll_interval_seconds)