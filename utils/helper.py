from datetime import datetime, timedelta, timezone


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
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ):
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


def compute_analytics(data_list: list) -> dict:
    """
    Computes comprehensive analytics across a list of GameData instances.
    """
    total_draws = len(data_list)
    if total_draws == 0:
        return {
            "total_draws": 0,
            "latest_draw": None,
            "color_counts": {"Red": 0, "Blue": 0, "Green": 0, "Yellow": 0, "None": 0},
            "color_percentages": {
                "Red": 0,
                "Blue": 0,
                "Green": 0,
                "Yellow": 0,
                "None": 0,
            },
            "hi_lo_mid": {"Hi": 0, "Lo": 0, "Mid": 0},
            "ball_freq": {n: 0 for n in range(1, 50)},
            "avg_total": 0,
        }

    latest_draw = data_list[0] if data_list else None
    color_counts = {"Red": 0, "Blue": 0, "Green": 0, "Yellow": 0, "None": 0}
    hi_lo_mid_counts = {"Hi": 0, "Lo": 0, "Mid": 0}
    ball_freq = {n: 0 for n in range(1, 50)}
    totals_sum = 0

    for item in data_list:
        col = item.colour if item.colour in color_counts else "None"
        color_counts[col] += 1

        hlm = item.hi_lo_mid if item.hi_lo_mid in hi_lo_mid_counts else "Mid"
        hi_lo_mid_counts[hlm] += 1

        totals_sum += item.total

        for ball_val in [
            item.first,
            item.second,
            item.third,
            item.fourth,
            item.fifth,
            item.sixth,
        ]:
            if 1 <= ball_val <= 49:
                ball_freq[ball_val] += 1

    color_percentages = {
        col: round((cnt / total_draws) * 100, 1)
        for col, cnt in color_counts.items()
        # if col != "None"
    }

    return {
        "total_draws": total_draws,
        "latest_draw": latest_draw,
        "color_counts": color_counts,
        "color_percentages": color_percentages,
        "hi_lo_mid": hi_lo_mid_counts,
        "ball_freq": ball_freq,
        "avg_total": round(totals_sum / total_draws, 1),
    }
