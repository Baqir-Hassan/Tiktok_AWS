from pathlib import Path

from app.providers.tts.base import TTSProvider


class CoquiTTSProvider(TTSProvider):
    provider_name = "coqui"

    def generate(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError("Coqui TTS is not enabled in this deployment")
