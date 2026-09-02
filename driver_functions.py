import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

from logger import get_logger

logger = get_logger("driver_functions")


def extract_draw_id(text: str) -> int | None:
    """
    Safely extract integer draw ID from raw element text using regex.
    """
    if not text:
        return None
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    return None


def check_id_of_current_draw(driver, current_draw: int, timeout: int = 60) -> int | None:
    """
    Checks the ID of the current draw and waits until the draw ID advances.
    :param driver: webdriver instance
    :param current_draw: the integer ID of the previous draw
    :param timeout: maximum seconds to wait for draw change
    :return: integer value of the new draw ID, or None if reading/waiting failed
    """
    wait = WebDriverWait(driver, timeout)
    try:
        elem = driver.find_element(By.CSS_SELECTOR, ".ball__holder-cd")
        raw_text = elem.text
        temp = extract_draw_id(raw_text)

        if temp is None:
            logger.warning(f"Could not parse draw ID from text: '{raw_text}'")
            return None

        if temp == current_draw:
            target_str = str(current_draw + 1)
            try:
                wait.until(
                    ec.text_to_be_present_in_element(
                        (By.CSS_SELECTOR, ".ball__holder-cd"), target_str
                    )
                )
            except TimeoutException:
                logger.warning(f"Timed out waiting for draw ID to become {target_str}")
                return None

        elem = driver.find_element(By.CSS_SELECTOR, ".ball__holder-cd")
        temp = extract_draw_id(elem.text)
        return temp

    except (NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
        logger.warning(f"WebDriver exception while checking draw ID: {e}")
        return None


def get_ball_values(driver, retries: int = 5, delay: float = 0.5) -> list[int] | None:
    """
    Retrieves the 6 ball numbers from the interface, retrying if values are loading.
    :param driver: webdriver instance
    :param retries: max attempts to read 6 complete ball values
    :param delay: delay between retries in seconds
    :return: list of 6 integers, or None if retrieval failed
    """
    for attempt in range(retries):
        try:
            draws = driver.find_element(
                By.CSS_SELECTOR,
                "div.draws > div.draws__ball-holder > div > div.ball__holder",
            )
            balls = draws.find_elements(
                By.CSS_SELECTOR, "div.animate > div.ball > div.ball-value"
            )

            if len(balls) < 6:
                time.sleep(delay)
                continue

            values = []
            for ball in balls:
                text = ball.text.strip()
                if text.isdigit():
                    values.append(int(text))
                else:
                    break

            if len(values) == 6:
                return values

        except (NoSuchElementException, StaleElementReferenceException, ValueError) as e:
            logger.debug(f"Attempt {attempt + 1}/{retries} reading ball values failed: {e}")

        time.sleep(delay)

    logger.warning("Failed to extract 6 complete ball values after retries")
    return None
