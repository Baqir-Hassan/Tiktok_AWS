from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Sage Studio Backend", alias="APP_NAME")
    app_display_name: str = Field(default="Sage Studio", alias="APP_DISPLAY_NAME")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    verification_token_expire_minutes: int = Field(default=60, alias="VERIFICATION_TOKEN_EXPIRE_MINUTES")
    verification_resend_cooldown_seconds: int = Field(default=60, alias="VERIFICATION_RESEND_COOLDOWN_SECONDS")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    database_url: str = Field(default="sqlite:///./saas.db", alias="DATABASE_URL")
    queue_provider: str = Field(default="database", alias="QUEUE_PROVIDER")
    initial_user_credits: int = Field(default=5, alias="INITIAL_USER_CREDITS")
    job_cost_credits: int = Field(default=1, alias="JOB_COST_CREDITS")
    job_rate_limit_count: int = Field(default=5, alias="JOB_RATE_LIMIT_COUNT")
    job_rate_limit_window_seconds: int = Field(default=3600, alias="JOB_RATE_LIMIT_WINDOW_SECONDS")
    worker_poll_interval_seconds: int = Field(default=10, alias="WORKER_POLL_INTERVAL_SECONDS")
    max_job_retries: int = Field(default=3, alias="MAX_JOB_RETRIES")
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    local_storage_path: Path = Field(default=BASE_DIR / "storage" / "videos", alias="LOCAL_STORAGE_PATH")
    public_media_base_url: str = Field(default="/media", alias="PUBLIC_MEDIA_BASE_URL")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_s3_endpoint_url: str | None = Field(default=None, alias="AWS_S3_ENDPOINT_URL")
    s3_bucket_name: str | None = Field(default=None, alias="S3_BUCKET_NAME")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    reddit_client_id: str | None = Field(default=None, alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str | None = Field(default=None, alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="tiktok-saas-backend/1.0", alias="REDDIT_USER_AGENT")
    tts_provider_default: str = Field(default="piper", alias="TTS_PROVIDER_DEFAULT")
    piper_binary: str = Field(default="piper", alias="PIPER_BINARY")
    piper_model_path: str = Field(default=str(BASE_DIR / "models" / "en_US-lessac-medium.onnx"), alias="PIPER_MODEL_PATH")
    piper_config_path: str | None = Field(default=None, alias="PIPER_CONFIG_PATH")
    piper_speaker_id: int | None = Field(default=None, alias="PIPER_SPEAKER_ID")
    piper_noise_scale: float = Field(default=0.667, alias="PIPER_NOISE_SCALE")
    piper_length_scale: float = Field(default=1.0, alias="PIPER_LENGTH_SCALE")
    piper_noise_w: float = Field(default=0.8, alias="PIPER_NOISE_W")
    edge_tts_voice: str = Field(default="en-US-SteffanNeural", alias="EDGE_TTS_VOICE")
    edge_tts_voice_male: str = Field(default="en-US-SteffanNeural", alias="EDGE_TTS_VOICE_MALE")
    edge_tts_voice_female: str = Field(default="en-US-AvaNeural", alias="EDGE_TTS_VOICE_FEMALE")
    edge_tts_use_gemini_gender_detection: bool = Field(default=False, alias="EDGE_TTS_USE_GEMINI_GENDER_DETECTION")
    edge_tts_gender_model: str = Field(default="llama-3.3-70b-versatile", alias="EDGE_TTS_GENDER_MODEL")
    edge_tts_rate: str = Field(default="+15%", alias="EDGE_TTS_RATE")
    edge_tts_volume: str = Field(default="+0%", alias="EDGE_TTS_VOLUME")
    edge_tts_pitch: str = Field(default="+0Hz", alias="EDGE_TTS_PITCH")
    edge_tts_max_retries: int = Field(default=3, alias="EDGE_TTS_MAX_RETRIES")
    whisper_model_size: str = Field(default="base", alias="WHISPER_MODEL_SIZE")
    minecraft_clip_path: str = Field(default=str(BASE_DIR / "assets" / "minecraft_loop.mp4"), alias="MINECRAFT_CLIP_PATH")
    tiktok_handle: str = Field(default="@YourTikTokHandle", alias="TIKTOK_HANDLE")
    ffmpeg_threads: int = Field(default=4, alias="FFMPEG_THREADS")
    render_backend: str = Field(default="moviepy", alias="RENDER_BACKEND")
    render_video_codec: str = Field(default="libx264", alias="RENDER_VIDEO_CODEC")
    render_audio_codec: str = Field(default="aac", alias="RENDER_AUDIO_CODEC")
    render_preset: str = Field(default="ultrafast", alias="RENDER_PRESET")
    render_amf_usage: str = Field(default="transcoding", alias="RENDER_AMF_USAGE")
    render_amf_quality: str = Field(default="balanced", alias="RENDER_AMF_QUALITY")
    render_video_bitrate: str | None = Field(default="5M", alias="RENDER_VIDEO_BITRATE")
    render_video_maxrate: str | None = Field(default="6M", alias="RENDER_VIDEO_MAXRATE")
    render_video_bufsize: str | None = Field(default="10M", alias="RENDER_VIDEO_BUFSIZE")
    title_font_path: str | None = Field(default=None, alias="TITLE_FONT_PATH")
    subtitle_font_path: str | None = Field(default=None, alias="SUBTITLE_FONT_PATH")
    handle_font_path: str | None = Field(default=None, alias="HANDLE_FONT_PATH")
    title_font_size: int = Field(default=55, alias="TITLE_FONT_SIZE")
    handle_font_size: int = Field(default=32, alias="HANDLE_FONT_SIZE")
    subtitle_font_size: int = Field(default=80, alias="SUBTITLE_FONT_SIZE")
    subtitle_stroke_width: int = Field(default=4, alias="SUBTITLE_STROKE_WIDTH")
    subtitle_words_per_chunk: int = Field(default=3, alias="SUBTITLE_WORDS_PER_CHUNK")
    subtitle_vertical_margin: int = Field(default=400, alias="SUBTITLE_VERTICAL_MARGIN")
    worker_api_key: str = Field(default="change-me-worker-key", alias="WORKER_API_KEY")
    worker_stale_timeout_minutes: int = Field(default=15, alias="WORKER_STALE_TIMEOUT_MINUTES")
    cors_allow_origins: str = Field(default="*", alias="CORS_ALLOW_ORIGINS")
    verify_email_page_url: str = Field(default="http://localhost:3000/verify-email", alias="VERIFY_EMAIL_PAGE_URL")
    reset_password_page_url: str = Field(default="http://localhost:3000/reset-password", alias="RESET_PASSWORD_PAGE_URL")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")

    def ensure_directories(self) -> None:
        self.local_storage_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
