from datetime import datetime

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    subreddit: str = Field(default="", max_length=128)
    tts_provider: str = Field(default="edge", pattern="^[a-z0-9_-]+$")
    custom_title: str | None = Field(default=None, max_length=512)
    custom_story: str | None = Field(default=None)


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
    source_post_id: str | None
    source_permalink: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    logs: list[JobLogResponse] = []


class JobListResponse(BaseModel):
    jobs: list[JobResponse]


class JobAccessResponse(BaseModel):
    url: str
    expires_in_seconds: int | None = None
