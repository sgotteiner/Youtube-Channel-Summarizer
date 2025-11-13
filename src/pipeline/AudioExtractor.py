"""
Module for extracting audio from video files.
"""
import logging
from pathlib import Path
# from moviepy.editor import VideoFileClip
from moviepy import VideoFileClip

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

    def extract_audio(self, video_path: Path, audio_path: Path) -> bool:
        """
        Extracts the audio track from a video file.

        If the audio file already exists, the extraction is skipped.

        Args:
            video_path (Path): The path to the source video file.
            audio_path (Path): The path where the extracted audio will be saved.

        Returns:
            bool: True if the audio was extracted successfully or already exists, False otherwise.
        """
        if audio_path.exists():
            self.logger.info(f"Audio for {video_path} already exists at {audio_path}. Skipping extraction.")
            return True

        audio_path.parent.mkdir(parents=True, exist_ok=True)
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
