# Gunicorn Configuration File
import threading
from scraper import scrape
from logger import get_logger

logger = get_logger("gunicorn_master")

# Server Socket
bind = "0.0.0.0:5000"
workers = 1
timeout = 120


def on_starting(server):
    """
    Gunicorn Master Server Lifecycle Hook.
    Executes ONCE in the Gunicorn Master Process before worker processes fork.
    Guarantees exactly ONE background scraper thread runs safely.
    """
    logger.info("Gunicorn Master process initializing background scraper thread...")
    scraper_thread = threading.Thread(
        target=scrape, daemon=True, name="GunicornScraperThread"
    )
    scraper_thread.start()
