import logging
import os
import subprocess
from pathlib import Path

import imageio_ffmpeg
from moviepy import AudioFileClip

from app.core.config import get_settings
from app.services.subtitle_service import SubtitleResult
from app.services.title_card_builder import TitleCardBuilder
from app.utils.text import sanitize_filename


LOGGER = logging.getLogger(__name__)


def _is_gpu_available() -> bool:
    """Return True when HWACCEL_DEVICE=cuda is set (i.e. running on Modal with a T4)."""
    return os.getenv("HWACCEL_DEVICE", "").lower() == "cuda"


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
            if _is_gpu_available():
                self._render_gpu(
                    audio_path=audio_path,
                    title_card_path=title_card_path,
                    subtitle_ass_path=subtitle_ass_path,
                    subtitles=subtitles,
                    output_path=output_path,
                )
            else:
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
                    "FFmpeg CPU renderer command: %s",
                    " ".join(f'"{part}"' if " " in part else part for part in command),
                )
                self._run(command)
        finally:
            title_card_path.unlink(missing_ok=True)
            subtitle_ass_path.unlink(missing_ok=True)

        return output_path, duration_seconds

    # ------------------------------------------------------------------
    # GPU two-pass path (NVDEC → scale_cuda/crop_cuda → NVENC, then
    # libass subtitle burn → NVENC re-encode)
    # ------------------------------------------------------------------

    def _render_gpu(
        self,
        audio_path: Path,
        title_card_path: Path,
        subtitle_ass_path: Path,
        subtitles: SubtitleResult,
        output_path: Path,
    ) -> None:
        """Two-pass GPU render:
        Pass 1 — NVDEC decode, scale_cuda/crop_cuda on GPU, software overlay for the
                  title card (brief, so PCIe cost is negligible), h264_nvenc encode.
        Pass 2 — libass subtitle burn (CPU-only filter, unavoidable) with h264_nvenc
                  re-encode; audio is stream-copied so it is not re-encoded.
        """
        pass1_path = output_path.parent / "_pass1_no_subs.mp4"
        try:
            cmd1 = self._build_command_gpu_pass1(
                audio_path=audio_path,
                title_card_path=title_card_path,
                subtitles=subtitles,
                output_path=pass1_path,
            )
            LOGGER.info(
                "FFmpeg GPU pass-1 command: %s",
                " ".join(f'"{p}"' if " " in p else p for p in cmd1),
            )
            self._run(cmd1)

            cmd2 = self._build_command_gpu_pass2(
                pass1_path=pass1_path,
                subtitle_ass_path=subtitle_ass_path,
                output_path=output_path,
            )
            LOGGER.info(
                "FFmpeg GPU pass-2 (subtitle burn) command: %s",
                " ".join(f'"{p}"' if " " in p else p for p in cmd2),
            )
            self._run(cmd2)
        finally:
            pass1_path.unlink(missing_ok=True)

    def _build_command_gpu_pass1(
        self,
        audio_path: Path,
        title_card_path: Path,
        subtitles: SubtitleResult,
        output_path: Path,
    ) -> list[str]:
        """
        GPU-accelerated background render (no subtitles).

        filter_complex breakdown:
          [0:v]  — looped Minecraft background, decoded by NVDEC (-hwaccel cuda).
                   scale_cuda and crop_cuda execute entirely in GPU memory, avoiding
                   any PCIe round-trip for the background stream.
          hwdownload — move the scaled/cropped frame back to CPU memory so the
                       software 'overlay' filter can composite the title card PNG.
                       This download only touches frames where the title card is
                       visible (first title_duration seconds), but FFmpeg's
                       enable= expression only skips blending — all frames still
                       pass through the filter graph, so the download happens for
                       every frame. Accepted trade-off: the overlay is brief.
          [2:v]  — looped static title card PNG (already in CPU memory, RGBA).
        """
        width, height = self.output_size
        title_duration = max(0.1, subtitles.title_duration)
        overlay_x = "(main_w-overlay_w)/2"
        overlay_y = "(main_h-overlay_h)/2"

        filter_complex = (
            # Step 1: GPU decode → GPU scale → GPU crop
            f"[0:v]scale_cuda={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop_cuda={width}:{height},"
            # Step 2: move frame from VRAM → system RAM for software overlay
            f"hwdownload,format=yuv420p[bg_soft];"
            # Step 3: overlay the title card PNG (CPU-side composite)
            f"[bg_soft][2:v]overlay={overlay_x}:{overlay_y}:"
            f"enable='between(t,0,{title_duration:.3f})'[v]"
        )

        command = [
            self.ffmpeg_exe,
            "-y",
            # ---- NVDEC hardware decode ----
            "-hwaccel", "cuda",
            "-hwaccel_output_format", "cuda",   # keep decoded frames in VRAM
            # ---- Inputs ----
            "-stream_loop", "-1",
            "-i", self.settings.minecraft_clip_path,
            "-i", str(audio_path),
            "-loop", "1",
            "-i", str(title_card_path),
            # ---- Filter graph ----
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "1:a:0",
            # ---- NVENC encode (no subtitles yet) ----
            "-c:v", "h264_nvenc",
            "-preset", self.settings.render_preset,   # e.g. "p4"
            "-rc", "vbr",
            "-cq", "28",
            "-c:a", self.settings.render_audio_codec,
            "-pix_fmt", "yuv420p",
            "-r", "24",
            "-shortest",
        ]

        # Optional bitrate caps (same settings as CPU path)
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

    def _build_command_gpu_pass2(
        self,
        pass1_path: Path,
        subtitle_ass_path: Path,
        output_path: Path,
    ) -> list[str]:
        """
        Subtitle burn pass.

        The input video is already 1080×1920 from pass 1, so the CPU only needs to
        run libass glyph rendering — no scaling, no decoding from raw source.
        NVENC re-encodes the subtitled frames; audio is stream-copied (not re-encoded).
        """
        escaped = self._escape_path_for_subtitles_filter(subtitle_ass_path)

        command = [
            self.ffmpeg_exe,
            "-y",
            "-i", str(pass1_path),
            # libass subtitle burn — CPU only, unavoidable
            "-vf", f"subtitles='{escaped}':charenc=UTF-8",
            # NVENC re-encode; audio copied to avoid quality loss from double-encode
            "-c:v", "h264_nvenc",
            "-preset", self.settings.render_preset,
            "-rc", "vbr",
            "-cq", "28",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
        ]

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

    # ------------------------------------------------------------------
    # CPU fallback path (original implementation, unchanged)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _run(self, command: list[str]) -> None:
        try:
            subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise RuntimeError(f"FFmpeg render failed: {stderr}") from exc

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
