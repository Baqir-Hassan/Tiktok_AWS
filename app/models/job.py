from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SCRAPING = "scraping"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_TTS = "generating_tts"
    GENERATING_SUBTITLES = "generating_subtitles"
    RENDERING_VIDEO = "rendering_video"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), default=JobStatus.QUEUED.value, nullable=False, index=True)
    subreddit: Mapped[str] = mapped_column(String(128), nullable=False)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_provider: Mapped[str] = mapped_column(String(64), default="piper", nullable=False)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_upload_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan", order_by="JobLog.timestamp")
    video = relationship("Video", back_populates="job", uselist=False, cascade="all, delete-orphan")
