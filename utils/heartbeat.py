"""Scraper heartbeat.

Reports actual scraper progress rather than process liveness: a beat is written
only when the scraper has handled a draw since the previous beat. If the
WebDriver loop hangs or keeps failing to produce draws, the beats stop, so a
log file that has not grown becomes the signal that scraping has stalled.
"""

import threading
import time

from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_INTERVAL_SECONDS = 5 * 60

_started = False
_lock = threading.Lock()
_last_progress_at = None
_last_progress_label = "no draw yet"
_progress_count = 0
_reported_count = 0


def record_progress(label: str) -> None:
    """Record that the scraper handled a draw. Called once per saved draw."""
    global _last_progress_at, _last_progress_label, _progress_count

    with _lock:
        _last_progress_at = time.time()
        _last_progress_label = label
        _progress_count += 1


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
    global _reported_count

    while True:
        time.sleep(interval_seconds)

        with _lock:
            # Nothing handled since the last beat: stay silent on purpose, so
            # the missing line shows up as log staleness.
            if _progress_count == _reported_count:
                continue
            _reported_count = _progress_count
            label = _last_progress_label
            age = time.time() - (_last_progress_at or time.time())

        # WARNING, not INFO: the file handler only records WARNING and above,
        # and the log file is the health signal.
        logger.warning("Heartbeat: scraper handled %s (%.0fs ago)", label, age)
