from threading import Thread
from flask import Flask, render_template, request

from models import storage
from helper_functions import decide_number_color
from scraper import scrape
from logger import get_logger

logger = get_logger("app")

app = Flask(__name__)

# Background Scraper Thread
scraper_thread = Thread(target=scrape, daemon=True, name="ScraperThread")


@app.teardown_appcontext
def close_db(error=None):
    """Closes storage session after requests."""
    storage.close()


@app.route("/")
def home():
    try:
        data = storage.all()
        data_list = [*data.values()][-1::-1] if data else []
    except Exception as e:
        logger.error(f"Error loading home page data: {e}")
        data_list = []

    return render_template(
        "index.html", data=data_list, color=decide_number_color, category="All"
    )


@app.route("/category", strict_slashes=False)
def category():
    try:
        hours = float(request.args.get("time", 0))
    except (ValueError, TypeError):
        hours = 0.0

    try:
        occurrence = int(request.args.get("occurrence", 1))
    except (ValueError, TypeError):
        occurrence = 1

    try:
        if hours > 0:
            temp_data = storage.time_diff(hours)
            category_label = f"{int(hours * 60)} mins" if hours < 1 else f"{int(hours)} hours"
        else:
            temp_data = storage.all()
            category_label = "All"

        temp_list = [*temp_data.values()][-1::-1] if temp_data else []

        if occurrence:
            data = [
                datum
                for datum in temp_list
                if (
                    datum.r_count == occurrence
                    or datum.g_count == occurrence
                    or datum.b_count == occurrence
                )
            ]
        else:
            data = temp_list

    except Exception as e:
        logger.error(f"Error loading category page data: {e}")
        data = []
        category_label = "Error"

    return render_template(
        "index.html", data=data, category=category_label, color=decide_number_color
    )


def start_scraper():
    if not scraper_thread.is_alive():
        logger.info("Starting background scraper thread...")
        scraper_thread.start()


if __name__ == "__main__":
    start_scraper()
    app.run()
