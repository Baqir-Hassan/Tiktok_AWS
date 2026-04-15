import logging

from worker.config import get_settings
from worker.runner import WorkerRunner


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    configure_logging()
    settings = get_settings()
    WorkerRunner(settings).run_forever()


if __name__ == "__main__":
    main()
