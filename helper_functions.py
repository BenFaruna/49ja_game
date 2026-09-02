def decide_number_color(num: int) -> tuple[int, str]:
    """
    From number decide the color in grid.
    :param num: number that will be used to determine color
    :return: tuple containing number and color string
    """
    try:
        num = int(num)
    except (ValueError, TypeError):
        return 0, "Unknown"

    grids = {
        (1, 13, 25, 37, 4, 16, 28, 40, 7, 19, 31, 43, 10, 22, 34, 46): "Red",
        (2, 14, 26, 38, 5, 17, 29, 41, 8, 20, 32, 44, 11, 23, 35, 47): "Blue",
        (3, 15, 27, 39, 6, 18, 30, 42, 9, 21, 33, 45, 12, 24, 36, 48): "Green",
        (49,): "Yellow",
    }

    for tup, color in grids.items():
        if num in tup:
            return num, color

    return num, "Unknown"


def total_category(nums: list) -> tuple[int, str]:
    """
    Gets the total of numbers passed to the function and returns the category (Lo, Mid, Hi)
    :param nums: list of integers
    :return: tuple containing (total, category_string)
    """
    if not nums:
        return 0, "Unknown"

    total = sum(nums)
    if 152 <= total <= 279:
        return total, "Hi"
    elif 149 <= total <= 151:
        return total, "Mid"
    elif 21 <= total <= 148:
        return total, "Lo"

    return total, "Unknown"


def color_count(nums: list) -> dict:
    """
    Counts occurrence of colors for the provided ball numbers.
    :param nums: list of integers
    :return: dictionary containing count of colors
    """
    color_num = {
        "Red": 0,
        "Blue": 0,
        "Green": 0,
        "Yellow": 0,
        "Unknown": 0,
    }

    for num in nums:
        _, color = decide_number_color(num)
        color_num[color] = color_num.get(color, 0) + 1

    return color_num


def color_decision(color_num: dict) -> str:
    """
    Decides the dominant color in a count dictionary. Returns 'None' if tied or invalid.
    :param color_num: dictionary containing color counts
    :return: string showing the dominant color
    """
    if not color_num:
        return "None"

    max_color = ("None", 0)
    for color, count in color_num.items():
        if color == "Unknown":
            continue
        if count > max_color[1]:
            max_color = (color, count)
        elif count == max_color[1] and count > 0:
            max_color = ("None", count)

    return max_color[0]


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
            "color_percentages": {"Red": 0, "Blue": 0, "Green": 0, "Yellow": 0},
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

        for ball_val in [item.first, item.second, item.third, item.fourth, item.fifth, item.sixth]:
            if 1 <= ball_val <= 49:
                ball_freq[ball_val] += 1

    color_percentages = {
        col: round((cnt / total_draws) * 100, 1)
        for col, cnt in color_counts.items()
        if col != "None"
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
