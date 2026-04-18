import asyncio
import logging
from pathlib import Path

import requests

from app.core.config import get_settings
from app.providers.tts.base import TTSProvider
from app.utils.text import expand_abbreviations_for_tts


LOGGER = logging.getLogger(__name__)


class EdgeTTSProvider(TTSProvider):
    provider_name = "edge"

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(self, text: str, output_path: Path) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("edge-tts is not installed. Install dependencies from requirements.txt.") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        speech_text = expand_abbreviations_for_tts(text).replace(".", ",")
        voice_id = self._resolve_voice_id(text)
        last_exception: Exception | None = None

        for _ in range(max(1, self.settings.edge_tts_max_retries)):
            try:
                communicate = edge_tts.Communicate(
                    speech_text,
                    voice=voice_id,
                    rate=self.settings.edge_tts_rate,
                    volume=self.settings.edge_tts_volume,
                    pitch=self.settings.edge_tts_pitch,
                )
                asyncio.run(communicate.save(str(output_path)))
                return output_path
            except Exception as exc:
                last_exception = exc

        raise RuntimeError(f"Edge TTS generation failed: {last_exception}") from last_exception

    def _resolve_voice_id(self, text: str) -> str:
        if not self.settings.edge_tts_use_gemini_gender_detection or not self.settings.google_api_key:
            return self.settings.edge_tts_voice

        try:
            detected_gender = self._detect_narrator_gender(text)
            if detected_gender == "female":
                return self.settings.edge_tts_voice_female
            return self.settings.edge_tts_voice_male
        except Exception:
            LOGGER.warning("Gemini narrator gender detection failed; using default Edge voice", exc_info=True)
            return self.settings.edge_tts_voice

    def _detect_narrator_gender(self, text: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.edge_tts_gender_model}:generateContent?key={self.settings.google_api_key}"
        )
        prompt = (
            "Analyze this Reddit story and determine the gender of the narrator/storyteller.\n\n"
            f"Story:\n{text}\n\n"
            "Respond with ONLY one word: either \"male\" or \"female\".\n"
            "Base your answer on:\n"
            "- First-person pronouns and context\n"
            "- References to relationships (my wife/husband, boyfriend/girlfriend)\n"
            "- Any explicit mentions of gender\n"
            "- Overall context clues\n\n"
            "Response (one word only):"
        )
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
        return "female" if "female" in raw else "male"
