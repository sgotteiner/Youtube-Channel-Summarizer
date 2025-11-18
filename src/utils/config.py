"""
Configuration module for the YouTube Channel Summarizer.

This module loads settings from the .config file and makes them available
as attributes of a Config instance. It provides type casting, default values,
and clear error handling for the application's configuration.
"""
import os
from typing import Optional
from dotenv import load_dotenv
from src.constants.service_constants import DEFAULT_MAX_VIDEO_LENGTH

class Config:
    """
    Loads configuration from a .config file and provides them as attributes.
    """
    def __init__(self):
        """
        Initializes the configuration by loading from the .env and .config files.
        It provides default values for any missing parameters.
        """
        # Load secrets from .env first, then settings from .config.
        # This allows environment variables to take precedence.
        load_dotenv(dotenv_path='.env')
        load_dotenv(dotenv_path='.config')

        self.channel_name = os.getenv('CHANNEL_NAME', 'Tech With Tim')
        
        self.num_videos_to_process = self._get_optional_int('NUM_VIDEOS_TO_PROCESS', 2)
        self.max_video_length = self._get_optional_int('MAX_VIDEO_LENGTH', DEFAULT_MAX_VIDEO_LENGTH)

        self.is_openai_runtime = self._get_bool('IS_OPENAI_RUNTIME', False)
        self.is_save_only_summaries = self._get_bool('IS_SAVE_ONLY_SUMMARIES', True)
        self.apply_max_length_for_captionless_only = self._get_bool('APPLY_MAX_LENGTH_FOR_CAPTIONLESS_ONLY', True)
        
        self.log_file_path = 'processing.log'

    def _get_bool(self, key: str, default: bool) -> bool:
        """Safely gets a boolean value from environment variables."""
        value = os.getenv(key)
        if value is None:
            return default
        return value.strip().lower() in ['true', '1', 't']

    def _get_optional_int(self, key: str, default: Optional[int]) -> Optional[int]:
        """Safely gets an optional integer from environment variables."""
        value = os.getenv(key)
        if value is None or value.strip() == '':
            return default
        try:
            return int(value)
        except ValueError:
            return default
