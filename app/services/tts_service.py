from app.core.config import get_settings
from app.providers.tts.base import TTSProvider
from app.providers.tts.chatterbox import ChatterboxTTSProvider
from app.providers.tts.coqui import CoquiTTSProvider
from app.providers.tts.piper import PiperTTSProvider


class TTSProviderFactory:
    def __init__(self) -> None:
        settings = get_settings()
        self.default_provider = settings.tts_provider_default
        self.providers: dict[str, type[TTSProvider]] = {
            PiperTTSProvider.provider_name: PiperTTSProvider,
            ChatterboxTTSProvider.provider_name: ChatterboxTTSProvider,
            CoquiTTSProvider.provider_name: CoquiTTSProvider,
        }

    def get_provider(self, provider_name: str | None = None) -> TTSProvider:
        resolved_name = (provider_name or self.default_provider).lower()
        provider_cls = self.providers.get(resolved_name)
        if not provider_cls:
            raise ValueError(f"Unsupported TTS provider: {resolved_name}")
        return provider_cls()
