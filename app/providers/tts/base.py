from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    provider_name: str

    @abstractmethod
    def generate(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError
