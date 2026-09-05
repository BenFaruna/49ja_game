import csv
import io
from datetime import datetime, timedelta, timezone
import math
from threading import Thread
from flask import Flask, render_template, request, jsonify, Response

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


def parse_datetime_param(dt_str, tz_offset=None):
    """
    Parses datetime string from query parameter.
    Converts to UTC naive datetime for database filtering.
    """
    if not dt_str or not dt_str.strip():
        return None
    dt_str = dt_str.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                pass
    if dt is None:
        return None

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    if tz_offset is not None:
        try:
            return dt + timedelta(minutes=float(tz_offset))
        except (ValueError, TypeError):
            pass
    return dt


def get_filtered_history_data(request_args):
    """Parses filter args and returns (filtered_list, category_label, selected_params)."""
    try:
        hours = float(request_args.get("time", 0))
    except (ValueError, TypeError):
        hours = 0.0

    try:
        occurrence = int(request_args.get("occurrence", 0))
    except (ValueError, TypeError):
        occurrence = 0

    start_str = request_args.get("start_datetime", "").strip()
    end_str = request_args.get("end_datetime", "").strip()

    try:
        tz_offset = float(request_args.get("tz_offset")) if request_args.get("tz_offset") else None
    except (ValueError, TypeError):
        tz_offset = None

    start_dt = parse_datetime_param(start_str, tz_offset)
    end_dt = parse_datetime_param(end_str, tz_offset)

    temp_data = storage.filter_draws(
        hours=hours,
        start_datetime=start_dt,
        end_datetime=end_dt,
        occurrence=occurrence,
    )

    temp_list = [*temp_data.values()][-1::-1] if temp_data else []

    if start_str and end_str:
        category_label = f"From {start_str.replace('T', ' ')} to {end_str.replace('T', ' ')}"
    elif start_str:
        category_label = f"From {start_str.replace('T', ' ')}"
    elif end_str:
        category_label = f"Up to {end_str.replace('T', ' ')}"
    elif hours > 0:
        category_label = f"{int(hours * 60)} mins" if hours < 1 else f"{int(hours)} hours"
    else:
        category_label = "All Time"

    if occurrence > 0:
        category_label += f" | {occurrence} Same Color"

    return temp_list, category_label, {
        "hours": hours,
        "occurrence": occurrence,
        "start_str": start_str,
        "end_str": end_str,
    }


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
    """Draw History Page with Range Filters, Pagination, and CSV Export support"""
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
            per_page = 100
    except (ValueError, TypeError):
        per_page = 25

    try:
        filtered_list, category_label, params = get_filtered_history_data(request.args)
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
        params = {"hours": 0, "occurrence": 0, "start_str": "", "end_str": ""}

    return render_template(
        "history.html",
        data=page_data,
        category=category_label,
        color=decide_number_color,
        selected_time=params["hours"],
        selected_occurrence=params["occurrence"],
        selected_start=params["start_str"],
        selected_end=params["end_str"],
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


@app.route("/history/export", strict_slashes=False)
def export_csv():
    """Export Filtered Draw History Data as CSV file download."""
    try:
        filtered_list, _, _ = get_filtered_history_data(request.args)

        output = io.StringIO()
        writer = csv.writer(output)

        # Write CSV Header
        writer.writerow(
            [
                "Draw ID",
                "Date & Time (UTC)",
                "Ball 1",
                "Ball 2",
                "Ball 3",
                "Ball 4",
                "Ball 5",
                "Ball 6",
                "Dominant Color",
                "Range",
                "Total",
                "Red Count",
                "Green Count",
                "Blue Count",
                "Yellow Count",
            ]
        )

        # Write Data Rows
        for item in filtered_list:
            writer.writerow(
                [
                    item.id,
                    item.date.strftime("%Y-%m-%d %H:%M:%S") if item.date else "",
                    item.first,
                    item.second,
                    item.third,
                    item.fourth,
                    item.fifth,
                    item.sixth,
                    item.colour,
                    item.hi_lo_mid,
                    item.total,
                    item.r_count,
                    item.g_count,
                    item.b_count,
                    item.y_count,
                ]
            )

        csv_filename = f"49ja_draw_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={csv_filename}"},
        )
    except Exception as e:
        logger.error(f"Error generating CSV export: {e}")
        return "Failed to generate CSV export.", 500



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
