from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import get_settings
from app.services.render_service import VideoRenderService
from app.services.subtitle_service import SubtitleService
from app.services.tts_service import TTSProviderFactory
from app.utils.text import sanitize_filename


def text_to_speech(text, filename="voiceover.wav"):
    return str(TTSProviderFactory().get_provider().generate(text, Path(filename)))


def make_video_from_script(title_text, narration_script, video_name="final_video.mp4", tiktok_name="MyTikTok"):
    settings = get_settings()
    with TemporaryDirectory(prefix="legacy-video-maker-") as temp_dir:
        audio_path = Path(temp_dir) / f"{sanitize_filename(title_text)}.wav"
        TTSProviderFactory().get_provider().generate(narration_script, audio_path)
        subtitles = SubtitleService().generate(audio_path, narration_script, title_text)
        VideoRenderService().render(
            title_text=title_text,
            tiktok_handle=tiktok_name or settings.tiktok_handle,
            audio_path=audio_path,
            subtitles=subtitles,
            output_path=Path(video_name),
        )
