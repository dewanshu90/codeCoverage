import logging
import os
from pythonjsonlogger import jsonlogger

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicate logs if called multiple times
    # This is important if setup_logging might be called more than once
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    # Create a JSON formatter
    # The %(message)s will include the log message and any extra dict passed
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s',
        json_ensure_ascii=False
    )

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional: Add a file handler for persistent logs
    # log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..\', '..\', 'app.log')
    # file_handler = logging.FileHandler(log_file_path)
    # file_handler.setFormatter(formatter)
    # logger.addHandler(file_handler)

    logging.info("Structured logging configured.")

