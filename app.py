import csv
import io
import math
import os
import time
import uuid
from datetime import datetime, timedelta
from threading import Thread

from flask import Flask, Response, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, InternalServerError

from models import storage
from routes import router
from routes_admin import admin_bp
from scraper import scrape
from utils.converter import decide_number_color
from utils.helper import compute_analytics
from utils.log_alerts import install_error_alert_handler
from utils.logger import get_logger, request_id_var

logger = get_logger(__name__)

# Email alerts for ERROR records; the handler rate limits itself.
install_error_alert_handler()

app = Flask(__name__)

# Secret key — required for Flask sessions. Set SECRET_KEY in your .env / environment.
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    logger.warning(
        "SECRET_KEY environment variable is not set! "
        "Using an insecure default — set it before deploying."
    )
    secret_key = "dev-insecure-secret-change-me"
app.secret_key = secret_key
app.permanent_session_lifetime = timedelta(hours=8)

# Requests slower than this are logged at WARNING so they reach the log file.
SLOW_REQUEST_MS = 1000

app.register_blueprint(router)
app.register_blueprint(admin_bp)


@app.before_request
def start_request_log():
    """Give every request an id so its log lines and tracebacks can be grouped."""
    request_id_var.set(uuid.uuid4().hex[:8])
    g.start_time = time.perf_counter()


@app.after_request
def log_request(response):
    """Log every request, flagging the slow ones."""
    started = g.get("start_time")
    if started is None:
        return response

    duration_ms = (time.perf_counter() - started) * 1000
    if duration_ms >= SLOW_REQUEST_MS:
        logger.warning(
            "Slow request: %s %s -> %s (%.0f ms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
    else:
        logger.info(
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
    return response


@app.errorhandler(Exception)
def log_unhandled_error(error):
    """Log unhandled exceptions with their traceback; keep HTTP errors intact."""
    if isinstance(error, HTTPException):
        return error

    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.path,
        error,
        exc_info=error,
    )
    return InternalServerError().get_response(request)

# Initialize the switch trigger monitor from persisted state
from utils.switch_service import initialize_from_db

initialize_from_db()


@app.teardown_appcontext
def close_db(error=None):
    """Closes storage session after requests."""
    storage.close()


def start_local_scraper():
    """Helper to start scraper thread when running via python app.py directly."""
    logger.info("Starting local scraper thread for dev server...")
    scraper_thread = Thread(target=scrape, daemon=True, name="DevScraperThread")
    scraper_thread.start()


if __name__ == "__main__":
    start_local_scraper()
    app.run(port=5050)
