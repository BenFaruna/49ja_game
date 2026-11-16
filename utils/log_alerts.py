"""Email alerts for ERROR-level log records, rate limited to avoid floods."""

import logging
import threading
import time

DEFAULT_COOLDOWN_SECONDS = 15 * 60

_ALERT_FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
)


class EmailAlertHandler(logging.Handler):
    """
    Sends at most one alert email per cooldown window.

    Errors that arrive during the window are counted and reported in the next
    email, so a crashing loop produces one message per window instead of
    hundreds.
    """

    def __init__(self, cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS):
        super().__init__(level=logging.ERROR)
        self.setFormatter(_ALERT_FORMATTER)
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._last_sent = 0.0
        self._suppressed = 0
        self._sending = False

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock:
            # Records produced while an alert is being sent must not recurse.
            if self._sending:
                return
            now = time.time()
            if now - self._last_sent < self.cooldown_seconds:
                self._suppressed += 1
                return
            self._last_sent = now
            suppressed, self._suppressed = self._suppressed, 0
            self._sending = True

        try:
            # Imported lazily so logging works even if email is unavailable.
            from utils.email_service import send_error_alert

            send_error_alert(self.format(record), suppressed)
        except Exception:
            # Alerting must never break logging or the caller.
            pass
        finally:
            with self._lock:
                self._sending = False


def install_error_alert_handler(
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
) -> EmailAlertHandler:
    """Attach the alert handler to the root logger once and return it."""
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, EmailAlertHandler):
            return handler

    handler = EmailAlertHandler(cooldown_seconds=cooldown_seconds)
    root.addHandler(handler)
    return handler
