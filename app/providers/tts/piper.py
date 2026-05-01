import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.providers.tts.base import TTSProvider
from app.utils.text import expand_abbreviations_for_tts


class PiperTTSProvider(TTSProvider):
    provider_name = "piper"

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            self.settings.piper_binary,
            "--model",
            self.settings.piper_model_path,
            "--output_file",
            str(output_path),
        ]
        if self.settings.piper_config_path:
            command.extend(["--config", self.settings.piper_config_path])
        if self.settings.piper_speaker_id is not None:
            command.extend(["--speaker", str(self.settings.piper_speaker_id)])
        command.extend(
            [
                "--noise_scale",
                str(self.settings.piper_noise_scale),
                "--length_scale",
                str(self.settings.piper_length_scale),
                "--noise_w",
                str(self.settings.piper_noise_w),
            ]
        )

        try:
            subprocess.run(
                command,
                input=expand_abbreviations_for_tts(text),
                text=True,
                capture_output=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Piper binary not found. Set PIPER_BINARY to the executable path.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Piper TTS generation failed: {exc.stderr.strip()}") from exc

        return output_path
