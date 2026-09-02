import math
from threading import Thread
from flask import Flask, render_template, request, jsonify

from models import storage
from helper_functions import decide_number_color, compute_analytics
from scraper import scrape
from logger import get_logger

logger = get_logger("app")

app = Flask(__name__)


@app.teardown_appcontext
def close_db(error=None):
    """Closes storage session after requests."""
    storage.close()


@app.route("/")
def home():
    """Dashboard Homepage with Time Filter"""
    try:
        hours = float(request.args.get("time", 0))
    except (ValueError, TypeError):
        hours = 0.0

    try:
        if hours > 0:
            temp_data = storage.time_diff(hours)
            category_label = f"{int(hours * 60)} mins" if hours < 1 else f"{int(hours)} hours"
        else:
            temp_data = storage.all()
            category_label = "All Time"

        data_list = [*temp_data.values()][-1::-1] if temp_data else []
        analytics = compute_analytics(data_list)
        recent_draws = data_list[:10]
    except Exception as e:
        logger.error(f"Error loading dashboard data: {e}")
        data_list = []
        analytics = compute_analytics([])
        recent_draws = []
        category_label = "All Time"

    return render_template(
        "dashboard.html",
        analytics=analytics,
        recent_draws=recent_draws,
        color=decide_number_color,
        selected_time=hours,
        category_label=category_label,
        active_tab="dashboard",
    )


@app.route("/history", strict_slashes=False)
def history():
    """Draw History Page with Filters and Pagination"""
    try:
        hours = float(request.args.get("time", 0))
    except (ValueError, TypeError):
        hours = 0.0

    try:
        occurrence = int(request.args.get("occurrence", 0))
    except (ValueError, TypeError):
        occurrence = 0

    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get("per_page", 25))
        if per_page < 1:
            per_page = 25
        elif per_page > 100:
            per_page = 100  # Cap at 100 max draws per page
    except (ValueError, TypeError):
        per_page = 25

    try:
        if hours > 0:
            temp_data = storage.time_diff(hours)
            category_label = f"{int(hours * 60)} mins" if hours < 1 else f"{int(hours)} hours"
        else:
            temp_data = storage.all()
            category_label = "All Time"

        temp_list = [*temp_data.values()][-1::-1] if temp_data else []

        if occurrence:
            filtered_list = [
                datum
                for datum in temp_list
                if (
                    datum.r_count == occurrence
                    or datum.g_count == occurrence
                    or datum.b_count == occurrence
                )
            ]
        else:
            filtered_list = temp_list

        total_items = len(filtered_list)
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_items)
        page_data = filtered_list[start_idx:end_idx]

        has_prev = page > 1
        has_next = page < total_pages

    except Exception as e:
        logger.error(f"Error loading history page data: {e}")
        page_data = []
        category_label = "Error"
        total_items = 0
        total_pages = 1
        page = 1
        has_prev = False
        has_next = False
        start_idx = 0
        end_idx = 0

    return render_template(
        "history.html",
        data=page_data,
        category=category_label,
        color=decide_number_color,
        selected_time=hours,
        selected_occurrence=occurrence,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_items=total_items,
        start_item=start_idx + 1 if total_items > 0 else 0,
        end_item=end_idx,
        has_prev=has_prev,
        has_next=has_next,
        active_tab="history",
    )


@app.route("/api/stats")
def api_stats():
    """JSON Endpoint for Live Dashboard Auto-Refresh (Supports ?time=X)"""
    try:
        hours = float(request.args.get("time", 0))
    except (ValueError, TypeError):
        hours = 0.0

    try:
        if hours > 0:
            temp_data = storage.time_diff(hours)
        else:
            temp_data = storage.all()

        data_list = [*temp_data.values()][-1::-1] if temp_data else []
        analytics = compute_analytics(data_list)

        latest = analytics["latest_draw"]
        latest_dict = None
        if latest:
            latest_dict = {
                "id": latest.id,
                "date": latest.date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "balls": [
                    latest.first,
                    latest.second,
                    latest.third,
                    latest.fourth,
                    latest.fifth,
                    latest.sixth,
                ],
                "colour": latest.colour,
                "total": latest.total,
                "hi_lo_mid": latest.hi_lo_mid,
                "counts": {
                    "Red": latest.r_count,
                    "Green": latest.g_count,
                    "Blue": latest.b_count,
                    "Yellow": latest.y_count,
                },
            }

        return jsonify(
            {
                "status": "success",
                "time_filter": hours,
                "total_draws": analytics["total_draws"],
                "latest_draw": latest_dict,
                "color_counts": analytics["color_counts"],
                "color_percentages": analytics["color_percentages"],
                "hi_lo_mid": analytics["hi_lo_mid"],
                "avg_total": analytics["avg_total"],
                "ball_freq": analytics["ball_freq"],
            }
        )
    except Exception as e:
        logger.error(f"Error in api_stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def start_local_scraper():
    """Helper to start scraper thread when running via python app.py directly."""
    logger.info("Starting local scraper thread for dev server...")
    scraper_thread = Thread(target=scrape, daemon=True, name="DevScraperThread")
    scraper_thread.start()


if __name__ == "__main__":
    start_local_scraper()
    app.run(port=5050)
