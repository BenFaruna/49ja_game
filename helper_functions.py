def decide_number_color(num: int) -> tuple[int, str]:
    """
    From number decide the color in grid
    :param num: number that will be used to determine color
    :return: tuple containing number and color
    """
    num = int(num)
    grids = {
        (1, 13, 25, 37, 4, 16, 28, 40, 7, 19, 31, 43, 10, 22, 34, 46): "Red",
        (2, 14, 26, 38, 5, 17, 29, 41, 8, 20, 32, 44, 11, 23, 35, 47): "Blue",
        (3, 15, 27, 39, 6, 18, 30, 42, 9, 21, 33, 45, 12, 24, 36, 48): "Green",
        (49,): "Yellow"
    }

    for tup in grids.keys():
        if num in tup:
            return num, grids[tup]


def total_category(nums: list) -> tuple[int, str]:
    """
    Gets the total of numbers passed to the function and return the category
    :param nums: variable arguments passed, should contain integers only
    :return: tuple a containing the total and category (Lo, Mid, Hi)
    """
    total = sum(nums)
    if 152 <= total <= 279:
        return total, "Hi"
    elif 149 <= total <= 151:
        return total, "Mid"
    if 21 <= total <= 148:
        return total, "Lo"


def color_count(nums: list) -> dict:
    """
    from the results get the color count and winning color from the count
    :param nums: variable arguments passed
    :return: dictionary containing count of colors of numbers in the grid
    """
    color_num = {
        "Red": 0,
        "Blue": 0,
        "Green": 0,
        "Yellow": 0
    }

    for num in nums:
        num_color = decide_number_color(num)
        color_num[num_color[1]] += 1

    return color_num


def color_decision(color_num: dict) -> str:
    """
    function decides the highest color in a dictionary and returns the highest color, or None if two are equal
    :param color_num: a dictionary containing color count
    :return: a string that shows the color with the highest count
    """
    max_color = ('None', 0)
    for color in color_num.items():
        if color[1] > max_color[1]:
            max_color = color
        elif color[1] == max_color[1]:
            max_color = ('None', max_color[1])
    return max_color[0]


# r = [1, 2, 14, 15, 13, 25]
# print(color_count(r))
# print(color_decision(color_count(r)))
