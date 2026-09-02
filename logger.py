import logging
import sys

def get_logger(name: str = "49ja_game", log_file: str = "app.log") -> logging.Logger:
    """
    Returns a logger configured to output to both console (stdout) and a log file.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setFormatter(formatter)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(log_file, encoding="utf-8")
    f_handler.setFormatter(formatter)
    logger.addHandler(f_handler)

    return logger
