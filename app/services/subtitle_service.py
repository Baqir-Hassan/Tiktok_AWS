from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path

import requests
from faster_whisper import WhisperModel
from moviepy import AudioFileClip

from app.core.config import get_settings
from app.utils.text import expand_abbreviations_for_tts, sanitize_whisper_subtitle_text


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
LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_whisper_model():
    return WhisperModel(
        settings.whisper_model_size,
        device="cuda",
        compute_type="float16"
    )


class SubtitleService:
    def generate(self, audio_path: Path, narration_script: str, title_text: str) -> SubtitleResult:
        try:
            whisper_result = self._generate_with_whisper(audio_path, narration_script, title_text)
            if whisper_result.chunks:
                return whisper_result
            LOGGER.warning("Whisper produced no subtitle chunks; falling back to heuristic subtitles")
            return self._generate_with_heuristics(audio_path, narration_script, title_text)
        except Exception:
            LOGGER.warning("Whisper subtitle generation failed; trying Gemini fallback", exc_info=True)
            try:
                gemini_result = self._generate_with_gemini_fallback(audio_path, narration_script, title_text)
                if gemini_result.chunks:
                    return gemini_result
            except Exception:
                LOGGER.warning("Gemini subtitle fallback failed; using local heuristic subtitles", exc_info=True)
            return self._generate_with_heuristics(audio_path, narration_script, title_text)

    def _generate_with_whisper(self, audio_path: Path, narration_script: str, title_text: str) -> SubtitleResult:
        model = load_whisper_model()
        prompt_text = expand_abbreviations_for_tts(narration_script)
        segments, _ = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
            initial_prompt=prompt_text,
        )
        transcription = {"segments": []}
        for segment in segments:
            transcription["segments"].append({
                "text": segment.text,
                "start": segment.start,
                "end": segment.end,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                    }
                    for w in (segment.words or [])
                ],
            })

        word_timestamps = self._extract_word_timestamps(transcription)
        detected_title_duration = self._get_actual_title_duration(transcription, title_text)
        title_duration = self._cap_title_duration(detected_title_duration, title_text)
        chunks = self._build_whisper_chunks(
            word_timestamps=word_timestamps,
            title_duration=title_duration,
            words_per_chunk=settings.subtitle_words_per_chunk,
        )
        if chunks:
            first_chunk_start = float(chunks[0]["start"])
            if first_chunk_start > max(6.0, title_duration + 3.0):
                LOGGER.warning(
                    "Detected late subtitle start at %.2fs; relaxing title intro duration",
                    first_chunk_start,
                )
                title_duration = min(title_duration, 3.8)
                chunks = self._build_whisper_chunks(
                    word_timestamps=word_timestamps,
                    title_duration=title_duration,
                    words_per_chunk=settings.subtitle_words_per_chunk,
                )

        with AudioFileClip(str(audio_path)) as audio_clip:
            audio_duration = float(audio_clip.duration)
        subtitle_chunks = [
            SubtitleChunk(
                text=chunk["text"],
                start=max(float(chunk["start"]), title_duration),
                end=min(audio_duration, max(float(chunk["end"]), float(chunk["start"]) + 0.1)),
            )
            for chunk in chunks
            if float(chunk["end"]) > title_duration
        ]
        return SubtitleResult(chunks=subtitle_chunks, title_duration=title_duration)

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

    def _extract_word_timestamps(self, transcription: dict) -> list[dict]:
        word_timestamps: list[dict] = []
        for segment in transcription.get("segments", []):
            for word_info in segment.get("words", []):
                word_text = word_info.get("word", "").strip()
                if not word_text:
                    continue
                word_timestamps.append(
                    {
                        "word": word_text,
                        "start": float(word_info.get("start", 0.0)),
                        "end": float(word_info.get("end", 0.0)),
                    }
                )
        return word_timestamps

    def _group_words_into_chunks(self, word_timestamps: list[dict], words_per_chunk: int = 3) -> list[dict]:
        chunks: list[dict] = []
        for index in range(0, len(word_timestamps), words_per_chunk):
            chunk_words = word_timestamps[index:index + words_per_chunk]
            if not chunk_words:
                continue
            chunks.append(
                {
                    "text": " ".join(word["word"] for word in chunk_words),
                    "start": chunk_words[0]["start"],
                    "end": chunk_words[-1]["end"],
                }
            )
        return chunks

    def _build_whisper_chunks(
        self,
        word_timestamps: list[dict],
        title_duration: float,
        words_per_chunk: int,
    ) -> list[dict]:
        if not word_timestamps:
            return []

        chunks = self._group_words_into_chunks(word_timestamps, words_per_chunk=max(1, words_per_chunk))
        cleaned_chunks: list[dict] = []
        for chunk in chunks:
            text = self._clean_transcribed_chunk_text(chunk["text"])
            if not text:
                continue
            if float(chunk["end"]) <= title_duration:
                continue
            cleaned_chunks.append(
                {
                    "text": text,
                    "start": float(chunk["start"]),
                    "end": float(chunk["end"]),
                }
            )
        return cleaned_chunks

    def _clean_transcribed_chunk_text(self, text: str) -> str:
        return sanitize_whisper_subtitle_text(text)
        # Remove hard transcription artifacts and normalize punctuation spacing.
        cleaned = text.replace("♪", " ")
        cleaned = cleaned.replace("[", " ").replace("]", " ")
        cleaned = cleaned.replace("(", " ").replace(")", " ")
        cleaned = " ".join(cleaned.split())
        return cleaned.strip()

    def _get_actual_title_duration(self, transcription: dict, title_text: str) -> float:
        title_words = [word.lower().strip(".,!?") for word in title_text.split()]
        all_words = self._extract_word_timestamps(transcription)
        heuristic_duration = max(1.5, len(title_words) / 3.0 + 0.5)
        if not all_words:
            return heuristic_duration

        # Keep matching near the beginning of narration so late repeated words
        # in the story body don't incorrectly extend title duration.
        search_window = max(30, len(title_words) * 6)
        candidate_words = all_words[:search_window]
        title_end_time = 0.0
        words_matched = 0
        for word in candidate_words:
            if words_matched >= len(title_words):
                break

            normalized_word = word["word"].lower().strip(".,!?")
            expected_word = title_words[words_matched]
            if expected_word in normalized_word or normalized_word in expected_word:
                words_matched += 1
                title_end_time = float(word["end"])

        title_end_time += 0.3
        if not title_words or words_matched < len(title_words) * 0.5:
            return heuristic_duration

        max_reasonable_duration = max(3.0, len(title_words) * 1.2 + 1.0)
        return min(title_end_time, max_reasonable_duration)

    def _cap_title_duration(self, detected_duration: float, title_text: str) -> float:
        title_word_count = max(1, len(title_text.split()))
        # Keep title intro short so subtitles don't disappear for too long.
        max_intro_seconds = min(8.0, max(3.2, title_word_count * 0.45 + 1.2))
        return min(detected_duration, max_intro_seconds)

    def _build_script_lines_for_subtitles(self, narration_script: str, words_per_chunk: int) -> list[str]:
        body_text = narration_script.split("\n\n", 1)[1] if "\n\n" in narration_script else narration_script
        words = body_text.split()
        return [" ".join(words[index:index + words_per_chunk]) for index in range(0, len(words), words_per_chunk)]

    def _merge_script_text_with_timing(
        self,
        script_lines: list[str],
        timing_chunks: list[dict],
        audio_duration: float,
        title_duration: float,
    ) -> list[SubtitleChunk]:
        if not script_lines:
            return []
        if not timing_chunks:
            return self._build_estimated_result_from_lines(script_lines, audio_duration, title_duration)

        merged: list[SubtitleChunk] = []
        count = min(len(script_lines), len(timing_chunks))
        for index in range(count):
            timing = timing_chunks[index]
            start = float(timing["start"])
            end = max(float(timing["end"]), start + 0.1)
            merged.append(SubtitleChunk(text=script_lines[index], start=start, end=end))

        if len(script_lines) > count:
            tail_lines = script_lines[count:]
            tail_start = merged[-1].end if merged else title_duration
            remaining = max(0.1, audio_duration - tail_start)
            per_chunk = remaining / max(1, len(tail_lines))
            cursor = tail_start
            for line in tail_lines:
                end = min(audio_duration, cursor + per_chunk)
                merged.append(SubtitleChunk(text=line, start=cursor, end=max(end, cursor + 0.1)))
                cursor = end

        return merged

    def _build_estimated_result_from_lines(
        self,
        lines: list[str],
        audio_duration: float,
        title_duration: float,
    ) -> list[SubtitleChunk]:
        playable_duration = max(0.1, audio_duration - title_duration)
        chunk_duration = playable_duration / max(1, len(lines))
        chunks: list[SubtitleChunk] = []
        start = title_duration
        for line in lines:
            end = start + chunk_duration
            chunks.append(SubtitleChunk(text=line, start=start, end=end))
            start = end
        return chunks
