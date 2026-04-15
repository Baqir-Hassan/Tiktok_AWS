import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerSettings:
    api_base_url: str
    worker_api_key: str
    worker_id: str
    poll_interval_seconds: int
    request_timeout_seconds: int
    api_retry_attempts: int
    api_retry_backoff_seconds: float
    heartbeat_interval_seconds: int
    aws_region: str
    s3_bucket: str
    s3_prefix: str
    public_s3_base_url: str | None
    local_work_dir: Path


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def get_settings() -> WorkerSettings:
    local_work_dir = Path(os.getenv("WORKER_LOCAL_DIR", Path.cwd() / ".worker-data")).resolve()
    local_work_dir.mkdir(parents=True, exist_ok=True)

    return WorkerSettings(
        api_base_url=_get_required_env("API_BASE_URL").rstrip("/"),
        worker_api_key=_get_required_env("WORKER_API_KEY"),
        worker_id=os.getenv("WORKER_ID", "local-worker-1").strip() or "local-worker-1",
        poll_interval_seconds=int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5")),
        request_timeout_seconds=int(os.getenv("WORKER_REQUEST_TIMEOUT_SECONDS", "30")),
        api_retry_attempts=int(os.getenv("WORKER_API_RETRY_ATTEMPTS", "3")),
        api_retry_backoff_seconds=float(os.getenv("WORKER_API_RETRY_BACKOFF_SECONDS", "1.5")),
        heartbeat_interval_seconds=int(os.getenv("WORKER_HEARTBEAT_INTERVAL_SECONDS", "30")),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        s3_bucket=_get_required_env("S3_BUCKET"),
        s3_prefix=os.getenv("S3_PREFIX", "videos").strip("/"),
        public_s3_base_url=os.getenv("PUBLIC_S3_BASE_URL", "").strip() or None,
        local_work_dir=local_work_dir,
    )
