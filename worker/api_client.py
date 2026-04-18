import logging
import time
from typing import Any

import requests

from worker.config import WorkerSettings
from worker.types import WorkerJob


LOGGER = logging.getLogger(__name__)


class WorkerApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class WorkerStopError(WorkerApiError):
    pass


class WorkerApiClient:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "X-Worker-Key": settings.worker_api_key,
            }
        )

    def get_next_job(self) -> WorkerJob | None:
        response = self._request("GET", "/jobs/next", expected_statuses={200, 204})
        if response.status_code == 204:
            return None
        return WorkerJob.from_api(response.json())

    def claim_job(self, job_id: int) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/jobs/{job_id}/claim",
            json={"worker_id": self.settings.worker_id},
            expected_statuses={200},
        ).json()

    def update_job(
        self,
        job_id: int,
        status: str,
        progress: int,
        message: str,
        source_title: str | None = None,
        source_post_id: str | None = None,
        source_permalink: str | None = None,
        script: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": status,
            "worker_id": self.settings.worker_id,
            "progress": progress,
            "message": message,
        }
        if source_title is not None:
            payload["source_title"] = source_title
        if source_post_id is not None:
            payload["source_post_id"] = source_post_id
        if source_permalink is not None:
            payload["source_permalink"] = source_permalink
        if script is not None:
            payload["script"] = script
        return self._request("POST", f"/jobs/{job_id}/update", json=payload, expected_statuses={200}).json()

    def complete_job(self, job_id: int, video_url: str, duration_seconds: float | None = None) -> dict[str, Any]:
        message = "Job completed"
        if duration_seconds is not None:
            message = f"Job completed (duration: {duration_seconds:.2f}s)"
        return self._request(
            "POST",
            f"/jobs/{job_id}/complete",
            json={"worker_id": self.settings.worker_id, "video_url": video_url, "message": message},
            expected_statuses={200},
        ).json()

    def fail_job(self, job_id: int, error_message: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/jobs/{job_id}/fail",
            json={
                "worker_id": self.settings.worker_id,
                "error_message": error_message,
                "message": f"Job failed: {error_message}",
            },
            expected_statuses={200},
        ).json()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        expected_statuses: set[int],
    ) -> requests.Response:
        url = f"{self.settings.api_base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(1, self.settings.api_retry_attempts + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    json=json,
                    timeout=self.settings.request_timeout_seconds,
                )
                if response.status_code in expected_statuses:
                    return response

                if response.status_code in {500, 502, 503, 504} and attempt < self.settings.api_retry_attempts:
                    LOGGER.warning(
                        "API %s %s failed with %s, retrying (%s/%s)",
                        method,
                        path,
                        response.status_code,
                        attempt,
                        self.settings.api_retry_attempts,
                    )
                    time.sleep(self.settings.api_retry_backoff_seconds * attempt)
                    continue

                self._raise_for_response(response)
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.settings.api_retry_attempts:
                    break
                LOGGER.warning(
                    "API %s %s raised %s, retrying (%s/%s)",
                    method,
                    path,
                    exc.__class__.__name__,
                    attempt,
                    self.settings.api_retry_attempts,
                )
                time.sleep(self.settings.api_retry_backoff_seconds * attempt)

        if last_error:
            raise RuntimeError(f"API request failed after retries: {method} {path}") from last_error
        raise RuntimeError(f"API request failed after retries: {method} {path}")

    def _raise_for_response(self, response: requests.Response) -> None:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text or f"HTTP {response.status_code}"
        if response.status_code in {404, 409, 410}:
            raise WorkerStopError(response.status_code, detail)
        raise WorkerApiError(response.status_code, detail)
