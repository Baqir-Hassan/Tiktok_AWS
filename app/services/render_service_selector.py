from app.core.config import get_settings
from app.services.render_service_ffmpeg import FFmpegVideoRenderService
from app.services.render_service import VideoRenderService


def create_video_renderer():
    settings = get_settings()
    backend = settings.render_backend.strip().lower()

    if backend == "moviepy":
        return VideoRenderService()
    if backend == "ffmpeg":
        return FFmpegVideoRenderService()

    raise ValueError(f"Unsupported render backend: {settings.render_backend}")
