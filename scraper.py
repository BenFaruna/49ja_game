import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager

from driver_functions import check_id_of_current_draw, get_ball_values
from helper_functions import color_count, color_decision, total_category
from logger import get_logger
from models.game_data import GameData

logger = get_logger("scraper")

# Driver Setup
_options = webdriver.FirefoxOptions()
_options.add_argument("--headless")
_options.add_argument("--no-sandbox")
_options.add_argument("--disable-dev-sh-usage")
_options.set_preference("permissions.default.image", 2)  # Block image loading
_options.set_preference(
    "permissions.default.stylesheet", 2
)  # Block CSS loading (optional)


def create_driver():
    """Create and return a new Firefox WebDriver instance."""
    service = FirefoxService(GeckoDriverManager().install())
    return webdriver.Firefox(service=service, options=_options)


def run_scraper_session():
    """
    Executes a single continuous scraping session.
    Restarts if consecutive failures or WebDriver exceptions occur.
    """
    driver = None
    try:
        logger.info("Initializing Firefox driver (Headless)...")
        driver = create_driver()
        wait = WebDriverWait(driver, 120)

        url = "https://logigames.bet9ja.com/Games/Launcher?gameId=11000&provider=0&sid=&pff=1&skin=201"
        logger.info(f"Navigating to {url}")
        driver.get(url)

        logger.info("Waiting for game interface elements to load...")
        wait.until(
            ec.presence_of_all_elements_located((By.CSS_SELECTOR, ".draws-mask"))
        )
        time.sleep(5)

        current_id = check_id_of_current_draw(driver, 0)
        if current_id is None:
            logger.warning(
                "Could not read initial draw ID. Restarting driver session..."
            )
            return

        logger.info(f"Initial draw ID detected: {current_id}")
        consecutive_failures = 0

        while True:
            next_id = check_id_of_current_draw(driver, current_id)
            if next_id is None:
                consecutive_failures += 1
                logger.warning(
                    f"Failed to check draw ID (failure count: {consecutive_failures}/5)"
                )
                if consecutive_failures >= 5:
                    logger.error(
                        "Max consecutive draw ID failures reached. Restarting driver session..."
                    )
                    break
                time.sleep(3)
                continue

            current_id = next_id
            current_draw = get_ball_values(driver)

            if not current_draw or len(current_draw) != 6:
                logger.warning(
                    f"Invalid ball values extracted: {current_draw}. Skipping saving this draw."
                )
                time.sleep(2)
                continue

            consecutive_failures = 0
            c_count = color_count(current_draw)
            c_decision = color_decision(c_count)
            total = total_category(current_draw)

            data = {
                "id": current_id - 1,
                "first": current_draw[0],
                "second": current_draw[1],
                "third": current_draw[2],
                "fourth": current_draw[3],
                "fifth": current_draw[4],
                "sixth": current_draw[5],
                "colour": c_decision,
                "total": total[0],
                "hi_lo_mid": total[1],
                "r_count": c_count["Red"],
                "g_count": c_count["Green"],
                "b_count": c_count["Blue"],
                "y_count": c_count["Yellow"],
            }

            logger.info(
                f"Scraped Draw #{data['id']}: Balls={current_draw}, Total={total[0]} ({total[1]}), Colour={c_decision}"
            )

            try:
                game_data = GameData(**data)
                game_data.save()
            except Exception as e:
                logger.error(f"Failed to save GameData #{data['id']} to database: {e}")

    except Exception as e:
        logger.error(f"Uncaught exception in scraper session: {e}", exc_info=True)
    finally:
        if driver:
            try:
                logger.info("Closing WebDriver session...")
                driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")


def scrape():
    """
    Main background scraping loop with automated crash recovery and reconnects.
    """
    logger.info("Starting resilient scraper background thread...")
    while True:
        try:
            run_scraper_session()
        except Exception as e:
            logger.error(f"Critical exception in scraper loop: {e}", exc_info=True)

        logger.info("Waiting 10 seconds before restarting scraper session...")
        time.sleep(10)
