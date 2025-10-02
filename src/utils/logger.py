import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(name: str = "youtube_summarizer", level: int = logging.INFO) -> logging.Logger:
    """
    Sets up a standardized logger for the application.

    Args:
        name (str): The name of the logger.
        level (int): The logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Ensure handlers are not duplicated if setup_logging is called multiple times
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

        # File handler (for persistent logs)
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{name}.log")
        
        # Rotate log file after 1 MB, keep 5 backups
        file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5)
        file_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    return logger