from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkerJob:
    id: int
    user_id: int
    status: str
    subreddit: str
    script: str | None
    tts_provider: str
    source_title: str | None
    source_text: str | None
    video_url: str | None
    uploaded_video_url: str | None
    video_upload_status: str
    error_message: str | None
    progress: int
    attempts: int
    claimed_by: str | None
    claimed_at: str | None
    heartbeat_at: str | None
    lease_expires_at: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "WorkerJob":
        return cls(**payload)
