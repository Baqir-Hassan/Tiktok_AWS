import logging
import os
import shutil
from pathlib import Path

from worker.config import get_settings
from worker.runner import WorkerRunner


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _prepend_path(path_value: str) -> None:
    existing_path = os.environ.get("PATH", "")
    path_parts = existing_path.split(os.pathsep) if existing_path else []
    if path_value and path_value not in path_parts:
        os.environ["PATH"] = os.pathsep.join([path_value, *path_parts]) if path_parts else path_value


def configure_ffmpeg_environment(ffmpeg_binary: str, local_work_dir: Path) -> Path:
    ffmpeg_path = Path(ffmpeg_binary).resolve()
    _prepend_path(str(ffmpeg_path.parent))

    alias_dir = (local_work_dir / "bin").resolve()
    alias_dir.mkdir(parents=True, exist_ok=True)
    alias_path = alias_dir / "ffmpeg.exe"

    # Whisper looks up "ffmpeg" by command name; create a stable alias if needed.
    if ffmpeg_path.name.lower() != "ffmpeg.exe":
        if (not alias_path.exists()) or (alias_path.stat().st_mtime < ffmpeg_path.stat().st_mtime):
            shutil.copy2(ffmpeg_path, alias_path)
        _prepend_path(str(alias_dir))

    os.environ["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg_path)
    return alias_path if alias_path.exists() else ffmpeg_path


def main() -> None:
    configure_logging()
    settings = get_settings()
    ffmpeg_command_path = configure_ffmpeg_environment(str(settings.ffmpeg_binary), settings.local_work_dir)
    logger = logging.getLogger(__name__)
    logger.info("Configured FFmpeg binary at %s", settings.ffmpeg_binary)
    logger.info("Configured FFmpeg command path at %s", ffmpeg_command_path)
    WorkerRunner(settings).run_forever()


if __name__ == "__main__":
    main()
