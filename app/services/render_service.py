import tempfile
import logging
from pathlib import Path

from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, TextClip, VideoFileClip, concatenate_videoclips
from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.services.subtitle_service import SubtitleResult
from app.utils.text import sanitize_filename


LOGGER = logging.getLogger(__name__)


class VideoRenderService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.output_size = (1080, 1920)

    def render(
        self,
        title_text: str,
        tiktok_handle: str,
        audio_path: Path,
        subtitles: SubtitleResult,
        output_path: Path,
    ) -> tuple[Path, float]:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with AudioFileClip(str(audio_path)) as audio:
            with VideoFileClip(self.settings.minecraft_clip_path) as background:
                background_clip = self._loop_video(background, float(audio.duration)).resized(new_size=self.output_size)
                title_card = self._create_title_card(title_text, tiktok_handle, subtitles.title_duration)
                subtitle_clips = self._create_subtitle_clips(subtitles)
                final_clip = CompositeVideoClip([background_clip, title_card, *subtitle_clips], size=self.output_size).with_audio(audio)
                try:
                    write_kwargs = {
                        "filename": str(output_path),
                        "fps": 24,
                        "codec": self.settings.render_video_codec,
                        "audio_codec": self.settings.render_audio_codec,
                        "threads": self.settings.ffmpeg_threads,
                        "logger": None,
                    }

                    ffmpeg_params: list[str] = []
                    if self.settings.render_video_codec.endswith("_amf"):
                        write_kwargs["preset"] = self.settings.render_amf_quality
                        ffmpeg_params.extend(
                            [
                                "-usage",
                                self.settings.render_amf_usage,
                            ]
                        )
                    else:
                        write_kwargs["preset"] = self.settings.render_preset

                    if ffmpeg_params:
                        write_kwargs["ffmpeg_params"] = ffmpeg_params

                    LOGGER.info(
                        "Rendering with codec=%s audio_codec=%s preset=%s ffmpeg_params=%s",
                        write_kwargs["codec"],
                        write_kwargs["audio_codec"],
                        write_kwargs.get("preset"),
                        ffmpeg_params or [],
                    )

                    final_clip.write_videofile(**write_kwargs)
                finally:
                    final_clip.close()
                    title_card.close()
                    background_clip.close()
                    for clip in subtitle_clips:
                        clip.close()

            return output_path, float(audio.duration)

    def _loop_video(self, clip: VideoFileClip, target_duration: float) -> VideoFileClip:
        if clip.duration >= target_duration:
            return clip.subclipped(0, target_duration)
        loop_count = int(target_duration / clip.duration) + 1
        return concatenate_videoclips([clip.copy() for _ in range(loop_count)], method="compose").subclipped(0, target_duration)

    def _create_title_card(self, title_text: str, tiktok_handle: str, duration: float) -> CompositeVideoClip:
        image_path = self._build_title_card_image()
        try:
            card_clip = ImageClip(str(image_path)).with_duration(duration).with_position("center")
            title_clip = TextClip(
                text=title_text,
                font_size=56,
                color="black",
                size=(780, 320),
                method="caption",
            ).with_duration(duration).with_position("center")
            handle_clip = TextClip(
                text=tiktok_handle,
                font_size=30,
                color="black",
            ).with_duration(duration).with_position((285, 790))
            return CompositeVideoClip([card_clip, title_clip, handle_clip], size=self.output_size)
        finally:
            image_path.unlink(missing_ok=True)

    def _build_title_card_image(self) -> Path:
        card_width = 900
        card_height = 400
        shadow_offset = 18
        image = Image.new("RGBA", (card_width + shadow_offset * 2, card_height + shadow_offset * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            [shadow_offset + 8, shadow_offset + 8, card_width + shadow_offset + 8, card_height + shadow_offset + 8],
            radius=30,
            fill=(0, 0, 0, 120),
        )
        draw.rounded_rectangle(
            [shadow_offset, shadow_offset, card_width + shadow_offset, card_height + shadow_offset],
            radius=30,
            fill=(255, 255, 255, 242),
        )
        draw.ellipse([50, 50, 100, 100], fill=(0, 0, 0, 255))
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        temp_file.close()
        path = Path(temp_file.name)
        image.save(path)
        return path

    def _create_subtitle_clips(self, subtitles: SubtitleResult) -> list[TextClip]:
        clips: list[TextClip] = []
        for chunk in subtitles.chunks:
            clips.append(
                TextClip(
                    text=chunk.text,
                    font_size=80,
                    color="white",
                    stroke_color="black",
                    stroke_width=4,
                    method="caption",
                    size=(980, None),
                )
                .with_position(("center", self.output_size[1] - 420))
                .with_start(chunk.start)
                .with_duration(max(0.1, chunk.end - chunk.start))
            )
        return clips

    def build_output_name(self, title_text: str) -> str:
        return f"{sanitize_filename(title_text)[:60]}.mp4"
