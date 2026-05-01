import logging
import subprocess
from pathlib import Path

import imageio_ffmpeg
from moviepy import AudioFileClip

from app.core.config import get_settings
from app.services.subtitle_service import SubtitleResult
from app.services.title_card_builder import TitleCardBuilder
from app.utils.text import sanitize_filename


LOGGER = logging.getLogger(__name__)


class FFmpegVideoRenderService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.output_size = (1080, 1920)
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.title_card_builder = TitleCardBuilder()

    def render(
        self,
        title_text: str,
        tiktok_handle: str,
        audio_path: Path,
        subtitles: SubtitleResult,
        output_path: Path,
    ) -> tuple[Path, float]:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with AudioFileClip(str(audio_path)) as audio_clip:
            duration_seconds = float(audio_clip.duration)

        title_card_path = self.title_card_builder.build(title_text=title_text, tiktok_handle=tiktok_handle)
        subtitle_ass_path = output_path.parent / "subtitles.ass"
        try:
            self._write_ass(subtitle_ass_path, subtitles)
            command = self._build_command(
                audio_path=audio_path,
                title_text=title_text,
                tiktok_handle=tiktok_handle,
                subtitles=subtitles,
                title_card_path=title_card_path,
                subtitle_ass_path=subtitle_ass_path,
                output_path=output_path,
            )
            LOGGER.info(
                "FFmpeg renderer command: %s",
                " ".join(f'"{part}"' if " " in part else part for part in command),
            )

            try:
                subprocess.run(command, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "").strip()
                raise RuntimeError(f"FFmpeg render failed: {stderr}") from exc
        finally:
            title_card_path.unlink(missing_ok=True)
            subtitle_ass_path.unlink(missing_ok=True)

        return output_path, duration_seconds

    def _build_command(
        self,
        audio_path: Path,
        title_text: str,
        tiktok_handle: str,
        subtitles: SubtitleResult,
        title_card_path: Path,
        subtitle_ass_path: Path,
        output_path: Path,
    ) -> list[str]:
        width, height = self.output_size
        base_video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
        title_duration = max(0.1, subtitles.title_duration)
        overlay_x = "(main_w-overlay_w)/2"
        overlay_y = "(main_h-overlay_h)/2"
        escaped_subtitle_path = self._escape_path_for_subtitles_filter(subtitle_ass_path)
        filter_complex = (
            f"[0:v]{base_video_filter}[bg];"
            f"[bg][2:v]overlay={overlay_x}:{overlay_y}:enable='between(t,0,{title_duration:.3f})'[with_title];"
            f"[with_title]subtitles='{escaped_subtitle_path}':charenc=UTF-8[v]"
        )

        command = [
            self.ffmpeg_exe,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            self.settings.minecraft_clip_path,
            "-i",
            str(audio_path),
            "-loop",
            "1",
            "-i",
            str(title_card_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-c:v",
            self.settings.render_video_codec,
            "-c:a",
            self.settings.render_audio_codec,
            "-pix_fmt",
            "yuv420p",
            "-r",
            "24",
            "-shortest",
        ]

        if self.settings.render_video_codec.endswith("_amf"):
            command.extend(
                [
                    "-usage",
                    self.settings.render_amf_usage,
                    "-preset",
                    self.settings.render_amf_quality,
                ]
            )
        else:
            command.extend(["-preset", self.settings.render_preset])

        if self.settings.render_video_bitrate:
            command.extend(["-b:v", self.settings.render_video_bitrate])
        if self.settings.render_video_maxrate:
            command.extend(["-maxrate", self.settings.render_video_maxrate])
        if self.settings.render_video_bufsize:
            command.extend(["-bufsize", self.settings.render_video_bufsize])

        if self.settings.ffmpeg_threads:
            command.extend(["-threads", str(self.settings.ffmpeg_threads)])

        command.append(str(output_path))
        return command

    def build_output_name(self, title_text: str) -> str:
        return f"{sanitize_filename(title_text)[:60]}.mp4"

    def _write_ass(self, subtitle_ass_path: Path, subtitles: SubtitleResult) -> None:
        font_name = "Luckiest Guy"
        margin_v = max(0, self.settings.subtitle_vertical_margin)
        style_line = (
            "Style: Default,"
            f"{font_name},"
            f"{self.settings.subtitle_font_size},"
            "&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
            f"0,0,0,0,100,100,0,0,1,{self.settings.subtitle_stroke_width},0,2,30,30,{margin_v},1"
        )
        header = "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "PlayResX: 1080",
                "PlayResY: 1920",
                "ScaledBorderAndShadow: yes",
                "",
                "[V4+ Styles]",
                "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
                "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
                "Alignment,MarginL,MarginR,MarginV,Encoding",
                style_line,
                "",
                "[Events]",
                "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
            ]
        )

        event_lines: list[str] = []
        for chunk in subtitles.chunks:
            start = self._format_ass_time(chunk.start)
            end = self._format_ass_time(max(chunk.end, chunk.start + 0.1))
            text = self._escape_ass_text(chunk.text)
            event_lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        subtitle_ass_path.write_text(
            header + ("\n" + "\n".join(event_lines) if event_lines else "\n"),
            encoding="utf-8",
        )

    @staticmethod
    def _format_ass_time(value: float) -> str:
        total_cs = int(max(0.0, value) * 100)
        hours = total_cs // 360000
        total_cs %= 360000
        minutes = total_cs // 6000
        total_cs %= 6000
        seconds = total_cs // 100
        centiseconds = total_cs % 100
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    @staticmethod
    def _escape_path_for_subtitles_filter(path: Path) -> str:
        escaped = str(path.resolve()).replace("\\", "/").replace(":", "\\:")
        return escaped.replace("'", "\\'")

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
