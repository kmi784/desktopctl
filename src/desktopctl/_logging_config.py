import logging
from pathlib import Path


def configure_logging(
    logger_levels: dict[str, int],
    default_level: int = logging.CRITICAL,
    log_file: str | Path | None = None,
) -> None:
    """Configure logging for one standalone debugging run."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file is not None:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=default_level,
        format=("%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s"),
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )

    for logger_name, level in logger_levels.items():
        logging.getLogger(logger_name).setLevel(level)
