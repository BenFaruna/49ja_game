import os
import time

import chromedriver_binary

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

# from webdriver_manager.chrome import ChromeDriverManager

from driver_functions import check_id_of_current_draw, get_ball_values
from helper_functions import color_count, color_decision, total_category
from models.game_data import GameData

# Driver Setup
_options = webdriver.ChromeOptions()
_options.binary_location = os.environ.get('GOOGLE_CHROME_BIN')
_options.add_argument('--headless') # comment this out if you want to see the browser
_options.add_argument('--no-sandbox')
_options.add_argument('--disable-dev-sh-usage')


def main():

    url = "https://logigames.bet9ja.com/Games/Launcher?gameId=11000&provider=0&sid=&pff=1&skin=201"
    driver = webdriver.Chrome(service=Service(), options=_options)


    wait = WebDriverWait(driver, 120)
    driver.get(url)

    wait.until(ec.presence_of_all_elements_located((By.CSS_SELECTOR, '.draws-mask')))
    time.sleep(5)
    current_id = check_id_of_current_draw(driver, 0)

# if __name__ == '__main__':
    while True:
        current_id = check_id_of_current_draw(driver, current_id)
        current_draw = get_ball_values(driver)
        c_count = color_count(current_draw)
        c_decision = color_decision(c_count)
        total = total_category(current_draw)

        data = {
            'id': current_id - 1,
            'first': current_draw[0],
            'second': current_draw[1],
            'third': current_draw[2],
            'fourth': current_draw[3],
            'fifth': current_draw[4],
            'sixth': current_draw[5],
            'colour': c_decision,
            'total': total[0],
            'hi_lo_mid': total[1],
            'r_count': c_count['Red'],
            'g_count': c_count['Green'],
            'b_count': c_count['Blue'],
            'y_count': c_count['Yellow'],
        }
        print(data)

        game_data = GameData(**data)
        game_data.save()
