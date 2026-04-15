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
                except WorkerStopError as exc:
                    LOGGER.warning("Job %s stopped due to control-plane response: %s", job.id, exc)
                except Exception as exc:
                    LOGGER.exception("Job %s failed", job.id)
                    try:
                        self.api_client.fail_job(job.id, str(exc))
                    except WorkerStopError as stop_exc:
                        LOGGER.warning("Job %s fail request aborted: %s", job.id, stop_exc)
            except WorkerStopError as exc:
                LOGGER.warning("Worker loop skipped job due to control-plane response: %s", exc)
            except Exception:
                LOGGER.exception("Worker loop iteration failed")
                time.sleep(self.settings.poll_interval_seconds)
