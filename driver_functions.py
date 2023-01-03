# import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

# from main import driver as web_driver, wait


def check_id_of_current_draw(driver, current_draw: int):
    """
    function checks the id of the current draw and permits movement of program when the draw has changed
    :param driver: webdriver to be used for locating elements
    :param current_draw: the recent draw that needs to change for code to progress
    :return: integer value of the current draw
    """
    wait = WebDriverWait(driver, 60)
    texts = driver.find_element(By.CSS_SELECTOR, '.ball__holder-cd')
    temp = int(texts.text.split()[-1])
    if temp == current_draw:
        wait.until(ec.text_to_be_present_in_element((By.CSS_SELECTOR, '.ball__holder-cd'), str(int(current_draw) + 1)))

    texts = driver.find_element(By.CSS_SELECTOR, '.ball__holder-cd')
    temp = int(texts.text.split()[-1])

    return temp


def get_ball_values(driver):
    """
    function to get the values of the ball from the interface
    :param driver: webdriver to be used for locating elements
    :return: a list of integers  containing six (6) integers
    """
    result = []
    draws = driver.find_element(By.CSS_SELECTOR, 'div.draws > div.draws__ball-holder > div > div.ball__holder')
    balls = draws.find_elements(By.CSS_SELECTOR, 'div.animate > div.ball > div.ball-value')
    try:
        for ball in balls:
            result.append(int(ball.text))
        return result
    except ValueError as e:
        print('Error:', e)
        return result
