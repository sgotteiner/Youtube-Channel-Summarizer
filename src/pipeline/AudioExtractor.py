"""
Module for extracting audio from video files.
"""
import logging
from pathlib import Path
from moviepy import VideoFileClip
from src.utils.common_logger import log_success_by_video_id, log_error_by_video_id


class AudioExtractor:
    """
    Extracts audio from a video file and saves it as a WAV file.
    """
    def __init__(self, logger: logging.Logger):
        """
        Initializes the AudioExtractor.

        Args:
            logger (logging.Logger): The logger instance for logging messages.
        """
        self.logger = logger

    def _check_file_exists(self, audio_path: Path, video_id: str) -> bool:
        """Check if the audio file already exists."""
        exists = audio_path.exists()
        if exists:
            self.logger.info(f"Audio for {audio_path} already exists at {audio_path}. Skipping extraction.")
            # Log the existence to the video_id format as well if provided
            if video_id:
                log_success_by_video_id(self.logger, video_id, "Audio extracted successfully to: %s", audio_path)
        return exists

    def _create_directories(self, audio_path: Path):
        """Create necessary directories for the audio file."""
        audio_path.parent.mkdir(parents=True, exist_ok=True)

    def _extract_audio_from_video(self, video_path: Path, audio_path: Path) -> bool:
        """Extract audio from video using moviepy."""
        try:
            self.logger.info(f"Starting audio extraction from {video_path} to {audio_path}...")
            with VideoFileClip(str(video_path)) as video:
                audio = video.audio
                # write_audiofile handles the conversion to WAV
                audio.write_audiofile(str(audio_path))

            self.logger.info(f"Audio extracted successfully from {video_path} to {audio_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error extracting audio from {video_path}: {e}")
            return False

    def extract_audio(self, video_path: Path, audio_path: Path, video_id: str = None) -> bool:
        """
        Extracts the audio track from a video file.

        If the audio file already exists, the extraction is skipped.

        Args:
            video_path (Path): The path to the source video file.
            audio_path (Path): The path where the extracted audio will be saved.
            video_id (str, optional): The video ID for logging purposes.

        Returns:
            bool: True if the audio was extracted successfully or already exists, False otherwise.
        """
        if self._check_file_exists(audio_path, video_id):
            return True

        self._create_directories(audio_path)
        
        success = self._extract_audio_from_video(video_path, audio_path)

        # Log completion status with video_id if provided
        if video_id:
            if success:
                log_success_by_video_id(self.logger, video_id, "Audio extracted successfully to: %s", audio_path)
            else:
                log_error_by_video_id(self.logger, video_id, "Failed to extract audio")

        return success