from datetime import datetime

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    subreddit: str = Field(..., min_length=2, max_length=128)
    tts_provider: str = Field(default="piper", pattern="^[a-z0-9_-]+$")


class JobLogResponse(BaseModel):
    stage: str
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: int
    status: str
    subreddit: str
    script: str | None
    tts_provider: str
    video_url: str | None
    uploaded_video_url: str | None
    video_upload_status: str
    error_message: str | None
    source_title: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    logs: list[JobLogResponse] = []


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
