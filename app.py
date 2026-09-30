import csv
import io
import math
import os
from datetime import datetime, timedelta
from threading import Thread

from flask import Flask, Response, jsonify, render_template, request

from models import storage
from routes import router
from routes_admin import admin_bp
from scraper import scrape
from utils.converter import decide_number_color
from utils.helper import compute_analytics
from utils.logger import get_logger

logger = get_logger(__name__, "server.log")

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

app.register_blueprint(router)
app.register_blueprint(admin_bp)

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
