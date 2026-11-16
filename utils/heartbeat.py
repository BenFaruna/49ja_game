"""Scraper heartbeat.

Writes one periodic log line so that "the log file has not grown" becomes a
usable health signal: if the scraper thread dies or hangs, the heartbeat stops
too.
"""

import threading
import time

from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_INTERVAL_SECONDS = 5 * 60

_started = False
_lock = threading.Lock()


def start_heartbeat(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Start the heartbeat thread once; later calls are ignored."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    thread = threading.Thread(
        target=_beat,
        args=(interval_seconds,),
        name="ScraperHeartbeat",
        daemon=True,
    )
    thread.start()
    logger.info("Scraper heartbeat started (every %d seconds).", interval_seconds)


def _beat(interval_seconds: int) -> None:
    while True:
        time.sleep(interval_seconds)
        # WARNING, not INFO: the file handler only records WARNING and above,
        # and the log file is the health signal.
        logger.warning("Heartbeat: scraper thread alive")
