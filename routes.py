import csv
import io
import math
from datetime import datetime, timedelta
from threading import Thread

from flask import Blueprint, Response, jsonify, render_template, request

from models import storage
from utils.converter import decide_number_color
from utils.helper import compute_analytics, parse_datetime_param
from utils.logger import get_logger

router = Blueprint("router", __name__)
logger = get_logger(__name__)

# The dashboard and history default to the last 30 minutes; an explicit
# ?time=0 still selects All Time.
DEFAULT_TIME_HOURS = 0.5

CSV_HEADER = (
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
)


def parse_hours(raw) -> float:
    """Parse the ``time`` filter, in hours.

    Missing or invalid values fall back to the 30-minute default; an explicit
    ``0`` still means All Time.
    """
    if raw is None or str(raw).strip() == "":
        return DEFAULT_TIME_HOURS
    try:
        return float(raw)
    except (ValueError, TypeError):
        return DEFAULT_TIME_HOURS


def window_label(hours: float) -> str:
    """Human label for a relative time window."""
    if hours and hours > 0:
        return f"{int(hours * 60)} mins" if hours < 1 else f"{int(hours)} hours"
    return "All Time"


@router.route("/")
def home():
    """Dashboard Homepage with Time Filter"""
    hours = parse_hours(request.args.get("time"))
    category_label = window_label(hours)

    try:
        analytics = storage.analytics(hours)
        recent_draws = storage.recent(10)
        if recent_draws:
            # The banner and preview always show the newest draws, even when
            # the selected window is empty.
            analytics["latest_draw"] = recent_draws[0]
    except Exception as e:
        logger.error(f"Error loading dashboard data: {e}")
        analytics = compute_analytics([])
        recent_draws = []

    return render_template(
        "dashboard.html",
        analytics=analytics,
        recent_draws=recent_draws,
        color=decide_number_color,
        selected_time=hours,
        category_label=category_label,
        active_tab="dashboard",
    )


@router.route("/history", strict_slashes=False)
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

    params = parse_history_filters(request.args)
    category_label = history_label(params)

    try:
        total_items = storage.count_draws(
            hours=params["hours"],
            start_datetime=params["start_dt"],
            end_datetime=params["end_dt"],
            occurrence=params["occurrence"],
        )
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        page_data = storage.page_draws(
            hours=params["hours"],
            start_datetime=params["start_dt"],
            end_datetime=params["end_dt"],
            occurrence=params["occurrence"],
            limit=per_page,
            offset=start_idx,
        )
        end_idx = start_idx + len(page_data)

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


@router.route("/history/export", strict_slashes=False)
def export_csv():
    """Export Filtered Draw History Data as CSV file download."""
    try:
        params = parse_history_filters(request.args)

        tz_offset = request.args.get("tz_offset", 0)
        tz_delta = timedelta(minutes=-float(tz_offset))

        draws = storage.iter_draws(
            hours=params["hours"],
            start_datetime=params["start_dt"],
            end_datetime=params["end_dt"],
            occurrence=params["occurrence"],
        )

        def generate():
            """Stream the CSV in chunks instead of holding every row at once."""
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(CSV_HEADER)

            pending = 0
            for item in draws:
                writer.writerow(
                    [
                        item.id,
                        (
                            (item.date + tz_delta).strftime("%Y-%m-%d %H:%M:%S")
                            if item.date
                            else ""
                        ),
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
                pending += 1
                if pending >= 1000:
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate(0)
                    pending = 0

            yield buffer.getvalue()

        csv_filename = (
            f"49ja_draw_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={csv_filename}"},
        )
    except Exception as e:
        logger.error(f"Error generating CSV export: {e}")
        return "Failed to generate CSV export.", 500


def serialize_draw(draw):
    """JSON shape used by the latest-draw banner and the recent draws table."""
    if not draw:
        return None
    return {
        "id": draw.id,
        "date": draw.date.strftime("%Y-%m-%dT%H:%M:%SZ") if draw.date else None,
        "balls": [
            draw.first,
            draw.second,
            draw.third,
            draw.fourth,
            draw.fifth,
            draw.sixth,
        ],
        "colour": draw.colour,
        "total": draw.total,
        "hi_lo_mid": draw.hi_lo_mid,
        "counts": {
            "Red": draw.r_count,
            "Green": draw.g_count,
            "Blue": draw.b_count,
            "Yellow": draw.y_count,
        },
    }


@router.route("/api/stats")
def api_stats():
    """JSON Endpoint for Live Dashboard Auto-Refresh (Supports ?time=X)"""
    hours = parse_hours(request.args.get("time"))

    try:
        analytics = storage.analytics(hours)

        recent_draws = storage.recent(10)
        latest_dict = serialize_draw(recent_draws[0]) if recent_draws else None

        return jsonify(
            {
                "status": "success",
                "time_filter": hours,
                "total_draws": analytics["total_draws"],
                "latest_draw": latest_dict,
                "recent_draws": [serialize_draw(draw) for draw in recent_draws],
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


@router.route("/switch-analytics", strict_slashes=False)
def switch_analytics():
    """Switch Trigger Analytics Page"""
    from utils.switch_service import get_alerts, get_tracker_states

    trackers = get_tracker_states()
    total_alerts, recent_alerts = get_alerts(limit=20, offset=0)

    # Determine danger level for the hero banner
    max_losses = max((t["overall_losses"] for t in trackers), default=0)
    if max_losses >= 8:
        danger_level = "critical"
    elif max_losses >= 6:
        danger_level = "warning"
    else:
        danger_level = "safe"

    return render_template(
        "switch_analytics.html",
        trackers=trackers,
        alerts=recent_alerts,
        total_alerts=total_alerts,
        danger_level=danger_level,
        max_losses=max_losses,
        active_tab="switch",
    )


@router.route("/api/switch-tracker/state")
def api_switch_tracker_state():
    """JSON endpoint for live switch tracker states."""
    try:
        from utils.switch_service import get_tracker_states

        trackers = get_tracker_states()
        max_losses = max((t["overall_losses"] for t in trackers), default=0)

        return jsonify(
            {
                "status": "success",
                "max_losses": max_losses,
                "trackers": trackers,
            }
        )
    except Exception as e:
        logger.error(f"Error in api_switch_tracker_state: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@router.route("/api/switch-tracker/alerts")
def api_switch_tracker_alerts():
    """JSON endpoint for switch trigger alert history."""
    try:
        from utils.switch_service import get_alerts

        try:
            limit = int(request.args.get("limit", 50))
            limit = max(1, min(limit, 200))
        except (ValueError, TypeError):
            limit = 50

        try:
            offset = int(request.args.get("offset", 0))
            offset = max(0, offset)
        except (ValueError, TypeError):
            offset = 0

        total, alerts = get_alerts(limit=limit, offset=offset)

        return jsonify(
            {
                "status": "success",
                "total_alerts": total,
                "limit": limit,
                "offset": offset,
                "alerts": alerts,
            }
        )
    except Exception as e:
        logger.error(f"Error in api_switch_tracker_alerts: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def parse_history_filters(request_args) -> dict:
    """Parse the history query string into values the storage layer can use."""
    try:
        occurrence = int(request_args.get("occurrence", 0))
    except (ValueError, TypeError):
        occurrence = 0

    start_str = request_args.get("start_datetime", "").strip()
    end_str = request_args.get("end_datetime", "").strip()

    try:
        tz_offset = (
            float(request_args.get("tz_offset"))
            if request_args.get("tz_offset")
            else None
        )
    except (ValueError, TypeError):
        tz_offset = None

    return {
        "hours": parse_hours(request_args.get("time")),
        "occurrence": occurrence,
        "start_str": start_str,
        "end_str": end_str,
        "start_dt": parse_datetime_param(start_str, tz_offset),
        "end_dt": parse_datetime_param(end_str, tz_offset),
    }


def history_label(params: dict) -> str:
    """Label describing the history filter currently applied."""
    if params["start_str"] and params["end_str"]:
        label = f"From {params['start_str'].replace('T', ' ')} to {params['end_str'].replace('T', ' ')}"
    elif params["start_str"]:
        label = f"From {params['start_str'].replace('T', ' ')}"
    elif params["end_str"]:
        label = f"Up to {params['end_str'].replace('T', ' ')}"
    else:
        label = window_label(params["hours"])

    if params["occurrence"] > 0:
        label += f" | {params['occurrence']} Same Color"

    return label
