"""
Logging utility for consistent service-level logging patterns.
"""
import logging


class ServiceLogger:
    """
    Provides consistent logging patterns for services, especially for video-specific logs.
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def info_video(self, video_id: str, message: str):
        """Log an info message with video_id prefix."""
        self.logger.info("[%s] %s", video_id, message)

    def error_video(self, video_id: str, message: str):
        """Log an error message with video_id prefix."""
        self.logger.error("[%s] %s", video_id, message)

    def warning_video(self, video_id: str, message: str):
        """Log a warning message with video_id prefix."""
        self.logger.warning("[%s] %s", video_id, message)

    def info_job(self, job_id: str, message: str):
        """Log an info message with job_id prefix."""
        self.logger.info("[Job: %s] %s", job_id, message)

    def error_job(self, job_id: str, message: str):
        """Log an error message with job_id prefix."""
        self.logger.error("[Job: %s] %s", job_id, message)