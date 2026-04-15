from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WorkerJobStage(StrEnum):
    SCRAPING = "scraping"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_TTS = "generating_tts"
    GENERATING_SUBTITLES = "generating_subtitles"
    RENDERING_VIDEO = "rendering_video"


class WorkerJobResponse(BaseModel):
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
    claimed_at: datetime | None
    heartbeat_at: datetime | None
    lease_expires_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class WorkerClaimRequest(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)


class WorkerClaimResponse(BaseModel):
    id: int
    status: str
    claimed: bool
    progress: int
    claimed_by: str | None
    claimed_at: datetime | None


class WorkerUpdateRequest(BaseModel):
    status: WorkerJobStage
    worker_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1)
    progress: int | None = Field(default=None, ge=0, le=100)
    source_title: str | None = Field(default=None, max_length=512)
    script: str | None = None


class WorkerCompleteRequest(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
    video_url: str = Field(..., min_length=1)
    message: str = Field(default="Job completed", min_length=1)


class WorkerFailRequest(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
    error_message: str = Field(..., min_length=1)
    message: str = Field(default="Job failed", min_length=1)


class WorkerHeartbeatRequest(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
