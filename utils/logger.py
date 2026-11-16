import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# All log files live in <project_root>/logs, regardless of the working directory.
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Every module writes to this single rotating log file.
LOG_FILE = LOG_DIR / "app.log"

# Rotate once the log file reaches 1MB, keeping 5 older files.
MAX_LOG_BYTES = 1 * 1024 * 1024
LOG_BACKUP_COUNT = 5

_FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
)

# One shared file handler: several handlers writing to the same rotating file
# would each rotate on their own counter and scatter lines across backups.
_file_handler = None


def _get_file_handler() -> RotatingFileHandler:
    global _file_handler
    if _file_handler is None:
        _file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        _file_handler.setLevel(logging.WARNING)
        _file_handler.setFormatter(_FORMATTER)
    return _file_handler


def get_logger(name: str = "49ja_game") -> logging.Logger:
    """
    Returns a logger configured to output to both console (stdout) and the
    shared rotating log file in the logs/ directory.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.DEBUG)
    c_handler.setFormatter(_FORMATTER)
    logger.addHandler(c_handler)

    # Rotating File Handler
    logger.addHandler(_get_file_handler())

    return logger
