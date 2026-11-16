import gzip
import logging
import os
import shutil
import sys
import time
from contextvars import ContextVar
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

# Backups older than this many days are deleted, even when rotation is idle.
LOG_RETENTION_DAYS = 30

# Request id stamped on records by app.py; "-" outside a web request.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


_REQUEST_ID_FILTER = RequestIdFilter()

_FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] [%(request_id)s]: %(message)s"
)

# One shared file handler: several handlers writing to the same rotating file
# would each rotate on their own counter and scatter lines across backups.
_file_handler = None


class GzipRotatingFileHandler(RotatingFileHandler):
    """
    Rotating file handler that gzips every backup.

    Backups are kept as ``app.log.1.gz`` ... ``app.log.N.gz``, capped at
    ``backupCount`` files, and any backup older than ``max_age_days`` is
    removed on startup and at every rollover, so a quiet period cannot leave
    stale logs behind and a busy one cannot grow without bound.
    """

    def __init__(self, *args, max_age_days: int | None = None, **kwargs):
        self.max_age_days = max_age_days
        super().__init__(*args, **kwargs)
        self.rotator = self._gzip_and_remove
        self._delete_expired()

    def rotation_filename(self, default_name: str) -> str:
        """Name every backup with a .gz suffix so shifts keep the extension."""
        return default_name + ".gz"

    @staticmethod
    def _gzip_and_remove(source: str, dest: str) -> None:
        with open(source, "rb") as src, gzip.open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(source)

    def doRollover(self) -> None:
        super().doRollover()
        self._delete_expired()

    def _delete_expired(self) -> None:
        if not self.max_age_days:
            return

        cutoff = time.time() - self.max_age_days * 86400
        prefix = os.path.basename(self.baseFilename) + "."
        directory = os.path.dirname(self.baseFilename) or "."

        for name in os.listdir(directory):
            if not name.startswith(prefix) or not name.endswith(".gz"):
                continue
            path = os.path.join(directory, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                # A concurrent rotation may have removed it already.
                continue


def _get_file_handler() -> GzipRotatingFileHandler:
    global _file_handler
    if _file_handler is None:
        _file_handler = GzipRotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            max_age_days=LOG_RETENTION_DAYS,
            encoding="utf-8",
        )
        _file_handler.setLevel(logging.WARNING)
        _file_handler.setFormatter(_FORMATTER)
        _file_handler.addFilter(_REQUEST_ID_FILTER)
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
    c_handler.addFilter(_REQUEST_ID_FILTER)
    logger.addHandler(c_handler)

    # Rotating File Handler
    logger.addHandler(_get_file_handler())

    return logger
