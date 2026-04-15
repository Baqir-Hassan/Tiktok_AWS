from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import requests
import whisper
from moviepy import AudioFileClip

from app.core.config import get_settings


@dataclass
class SubtitleChunk:
    text: str
    start: float
    end: float


@dataclass
class SubtitleResult:
    chunks: list[SubtitleChunk]
    title_duration: float


settings = get_settings()


@lru_cache(maxsize=1)
def load_whisper_model():
    return whisper.load_model(settings.whisper_model_size)


class SubtitleService:
    def generate(self, audio_path: Path, narration_script: str, title_text: str) -> SubtitleResult:
        try:
            return self._generate_with_whisper(audio_path, narration_script, title_text)
        except Exception:
            return self._generate_with_gemini_fallback(audio_path, narration_script, title_text)

    def _generate_with_whisper(self, audio_path: Path, narration_script: str, title_text: str) -> SubtitleResult:
        model = load_whisper_model()
        transcription = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
            initial_prompt=narration_script,
        )

        chunks: list[SubtitleChunk] = []
        title_duration = 0.0
        matched_title_words = 0
        title_words = [word.strip(".,!?").lower() for word in title_text.split()]
        pending_words: list[dict] = []

        for segment in transcription.get("segments", []):
            for word in segment.get("words", []):
                word_text = word.get("word", "").strip()
                if not word_text:
                    continue
                normalized = word_text.strip(".,!?").lower()
                if matched_title_words < len(title_words) and normalized == title_words[matched_title_words]:
                    matched_title_words += 1
                    title_duration = max(title_duration, float(word["end"]))
                pending_words.append(
                    {"text": word_text, "start": float(word["start"]), "end": float(word["end"])}
                )
                if len(pending_words) == 3:
                    chunks.append(
                        SubtitleChunk(
                            text=" ".join(item["text"] for item in pending_words),
                            start=pending_words[0]["start"],
                            end=pending_words[-1]["end"],
                        )
                    )
                    pending_words = []

        if pending_words:
            chunks.append(
                SubtitleChunk(
                    text=" ".join(item["text"] for item in pending_words),
                    start=pending_words[0]["start"],
                    end=pending_words[-1]["end"],
                )
            )

        if title_duration == 0.0:
            title_duration = max(1.5, len(title_words) / 2.5)

        filtered_chunks = [chunk for chunk in chunks if chunk.start >= title_duration]
        return SubtitleResult(chunks=filtered_chunks or chunks, title_duration=title_duration + 0.25)

    def _generate_with_gemini_fallback(self, audio_path: Path, narration_script: str, title_text: str) -> SubtitleResult:
        if not settings.google_api_key:
            return self._generate_with_heuristics(audio_path, narration_script, title_text)

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={settings.google_api_key}"
        )
        prompt = (
            "Split this narration into short subtitle chunks of 2 to 5 words each. "
            "Return one subtitle chunk per line, with no numbering.\n\n"
            f"{narration_script}"
        )
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        response.raise_for_status()
        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        lines = [line.strip("-• ").strip() for line in raw_text.splitlines() if line.strip()]
        return self._build_estimated_result(audio_path, lines, title_text)

    def _generate_with_heuristics(self, audio_path: Path, narration_script: str, title_text: str) -> SubtitleResult:
        words = narration_script.split()
        lines = [" ".join(words[index:index + 4]) for index in range(0, len(words), 4)]
        return self._build_estimated_result(audio_path, lines, title_text)

    def _build_estimated_result(self, audio_path: Path, lines: list[str], title_text: str) -> SubtitleResult:
        with AudioFileClip(str(audio_path)) as audio_clip:
            audio_duration = float(audio_clip.duration)

        title_duration = max(1.5, len(title_text.split()) / 2.5)
        playable_duration = max(0.1, audio_duration - title_duration)
        chunk_duration = playable_duration / max(1, len(lines))

        chunks: list[SubtitleChunk] = []
        start = title_duration
        for line in lines:
            end = start + chunk_duration
            chunks.append(SubtitleChunk(text=line, start=start, end=end))
            start = end
        return SubtitleResult(chunks=chunks, title_duration=title_duration)
