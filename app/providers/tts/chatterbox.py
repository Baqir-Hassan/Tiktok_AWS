from pathlib import Path

from app.providers.tts.base import TTSProvider


class ChatterboxTTSProvider(TTSProvider):
    provider_name = "chatterbox"

    def generate(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError("Chatterbox TTS is reserved for a future GPU-backed upgrade")
