from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TikTok SaaS Backend"
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440
    jwt_algorithm: str = "HS256"
    database_url: str = "sqlite:///./saas.db"
    initial_user_credits: int = 5
    job_cost_credits: int = 1
    job_rate_limit_count: int = 5
    job_rate_limit_window_seconds: int = 3600
    worker_poll_interval_seconds: int = 5
    max_job_retries: int = 3
    storage_backend: str = "local"
    local_storage_path: Path = BASE_DIR / "storage" / "videos"
    public_media_base_url: str = "/media"
    aws_region: str = "us-east-1"
    s3_bucket_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    google_api_key: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "tiktok-saas-backend/1.0"
    tts_provider_default: str = "piper"
    piper_binary: str = "piper"
    piper_model_path: str = str(BASE_DIR / "models" / "en_US-lessac-medium.onnx")
    piper_config_path: str | None = None
    piper_speaker_id: int | None = None
    piper_noise_scale: float = 0.667
    piper_length_scale: float = 1.0
    piper_noise_w: float = 0.8
    whisper_model_size: str = "base"
    minecraft_clip_path: str = str(BASE_DIR / "assets" / "minecraft_loop.mp4")
    tiktok_handle: str = "@YourTikTokHandle"
    ffmpeg_threads: int = 4
    render_video_codec: str = "libx264"
    render_audio_codec: str = "aac"
    render_preset: str = "ultrafast"
    render_amf_usage: str = "transcoding"
    render_amf_quality: str = "speed"
    worker_api_key: str = "change-me-worker-key"
    worker_stale_timeout_minutes: int = 15

    def ensure_directories(self) -> None:
        self.local_storage_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
