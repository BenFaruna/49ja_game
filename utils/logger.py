import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# All log files live in <project_root>/logs, regardless of the working directory.
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Rotate once a log file reaches 1MB, keeping 5 older files.
MAX_LOG_BYTES = 1 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def get_logger(name: str = "49ja_game", log_file: str = "app.log") -> logging.Logger:
    """
    Returns a logger configured to output to both console (stdout) and a log file.
    Log files are written to the logs/ directory and rotate at 1MB.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
    )

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.DEBUG)
    c_handler.setFormatter(formatter)
    logger.addHandler(c_handler)

    # Rotating File Handler
    log_path = LOG_DIR / Path(log_file).name
    f_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    f_handler.setLevel(logging.WARNING)
    f_handler.setFormatter(formatter)
    logger.addHandler(f_handler)

    return logger
