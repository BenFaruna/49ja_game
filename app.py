import csv
import io
import math
from datetime import datetime
from threading import Thread

from flask import Flask, Response, jsonify, render_template, request

from models import storage
from routes import router
from scraper import scrape
from utils.converter import decide_number_color
from utils.helper import compute_analytics
from utils.logger import get_logger

logger = get_logger("app")

app = Flask(__name__)
app.register_blueprint(router)


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
