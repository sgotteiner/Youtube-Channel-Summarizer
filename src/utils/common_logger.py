"""
Common logging utility functions to eliminate duplicate code across the system.
"""
import logging
from pathlib import Path
from typing import Optional
from src.constants.service_constants import MAX_FILENAME_LENGTH


def log_success_by_video_id(logger: logging.Logger, video_id: str, message: str, *args):
    """
    Standardized logging for success messages with video_id format.
    """
    logger.info(f"[{video_id}] {message}", *args)


def log_error_by_video_id(logger: logging.Logger, video_id: str, message: str, *args):
    """
    Standardized logging for error messages with video_id format.
    """
    logger.error(f"[{video_id}] {message}", *args)


def log_warning_by_video_id(logger: logging.Logger, video_id: str, message: str, *args):
    """
    Standardized logging for warning messages with video_id format.
    """
    logger.warning(f"[{video_id}] {message}", *args)


def validate_file_path(logger: logging.Logger, file_path: Path, video_id: str) -> Optional[Path]:
    """Validate that the specified file path exists and return it as Path object."""
    if not file_path:
        log_error_by_video_id(logger, video_id, "File path is None")
        return None

    if not file_path.exists():
        log_error_by_video_id(logger, video_id, "File does not exist: %s", file_path)
        return None

    return file_path


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from a string to make it a valid filename."""
    import re
    sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
    # Replace spaces with underscores as requested
    sanitized = sanitized.replace(' ', '_')
    return sanitized[:MAX_FILENAME_LENGTH]