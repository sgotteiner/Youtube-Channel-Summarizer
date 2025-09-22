import logging

class Logger:
    def __init__(self, name, log_file, level=logging.INFO):
        """
        Initializes the logger.

        Args:
            name (str): The name of the logger.
            log_file (str): The file to which the logs will be written.
            level (int): The logging level.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Create a file handler
        handler = logging.FileHandler(log_file)
        handler.setLevel(level)

        # Create a logging format
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        # Add the handlers to the logger
        if not self.logger.handlers:
            self.logger.addHandler(handler)

    def get_logger(self):
        """
        Returns the logger instance.
        """
        return self.logger
