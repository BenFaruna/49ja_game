from models import storage
from utils.helper import parse_datetime_param


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
        tz_offset = (
            float(request_args.get("tz_offset"))
            if request_args.get("tz_offset")
            else None
        )
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
        category_label = (
            f"From {start_str.replace('T', ' ')} to {end_str.replace('T', ' ')}"
        )
    elif start_str:
        category_label = f"From {start_str.replace('T', ' ')}"
    elif end_str:
        category_label = f"Up to {end_str.replace('T', ' ')}"
    elif hours > 0:
        category_label = (
            f"{int(hours * 60)} mins" if hours < 1 else f"{int(hours)} hours"
        )
    else:
        category_label = "All Time"

    if occurrence > 0:
        category_label += f" | {occurrence} Same Color"

    return (
        temp_list,
        category_label,
        {
            "hours": hours,
            "occurrence": occurrence,
            "start_str": start_str,
            "end_str": end_str,
        },
    )
