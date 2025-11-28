"""
Module for downloading YouTube audio and captions.
"""
from pathlib import Path
from typing import Optional
import logging
from yt_dlp import YoutubeDL
from src.utils.common_logger import log_success_by_video_id, log_error_by_video_id, log_warning_by_video_id, sanitize_filename
from src.constants.service_constants import AUDIO_FILE_EXTENSION, CAPTION_FILE_EXTENSION


class AudioDownloader:
    """Handles the downloading of audio from YouTube videos and captions."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _check_file_exists_and_log(self, filepath: Path, title: str, video_id: str, file_type: str) -> Optional[Path]:
        """Check if the file already exists and log appropriately."""
        if filepath.exists():
            self.logger.info(f"{file_type} '{title}' already exists. Skipping download.")
            # Log the completion status with video_id format too
            log_success_by_video_id(self.logger, video_id, f"{file_type} downloaded successfully to: %s", filepath)
            return filepath
        return None

    def download_audio(self, youtube_video_url: str, video_title: str, upload_date: str, video_id: str, path_to_save_audio: Path) -> Optional[Path]:
        """
        Downloads audio from a YouTube URL and converts to WAV format using yt-dlp.

        Args:
            youtube_video_url (str): The YouTube URL to download from
            video_title (str): Title of the video (for filename)
            upload_date (str): Upload date of the video
            video_id (str): The video ID for logging purposes
            path_to_save_audio (Path): Path where the audio will be saved

        Returns:
            Optional[Path]: Path to the downloaded audio in WAV format, or None if failed
        """
        sanitized_filename = f"{sanitize_filename(video_title)}-{upload_date}-{video_id}"
        # Note: yt-dlp will add the .wav extension automatically
        audio_filepath = path_to_save_audio / f"{sanitized_filename}.wav"

        # Check if file already exists
        existing_file = self._check_file_exists_and_log(audio_filepath, video_title, video_id, "Audio")
        if existing_file:
            return existing_file

        ydl_opts = {
            'format': 'bestaudio/best',  # Download the best available audio
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',      # Convert to WAV format
                'preferredquality': '0',      # Highest quality
            }],
            'postprocessor_args': [
                '-ar', '16000',  # Optional: set audio sampling rate
            ],
            'prefer_ffmpeg': True,
            'extractaudio': True,
            'keepvideo': False,
            'outtmpl': str(path_to_save_audio / f'{sanitized_filename}.%(ext)s'),  # Output path with filename
        }

        try:
            self.logger.info(f"Downloading audio to {audio_filepath}...")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_video_url])

            self.logger.info("Audio download and conversion successful.")

            # Log the completion status with video_id format
            log_success_by_video_id(self.logger, video_id, "Audio downloaded successfully to: %s", audio_filepath)
            return audio_filepath
        except Exception as e:
            self.logger.error(f'Error downloading or converting audio: {e}')
            log_error_by_video_id(self.logger, video_id, "Failed to download or convert audio")
            return None

    def download_captions(self, video_id: str, destination_path: Path) -> Optional[Path]:
        """
        Downloads the English captions for a video to the specified path.
        Returns the path to the downloaded .vtt file if successful, otherwise None.
        """
        self.logger.info(f"Attempting to download captions for video ID: {video_id}")

        # yt-dlp expects a path template without the extension
        outtmpl = destination_path / '%(title)s-%(upload_date)s-%(id)s.%(ext)s'

        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'subtitleslangs': ['en'],
            'outtmpl': str(outtmpl),
            'quiet': True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            # Search for the downloaded .vtt file
            for file in destination_path.glob(f'*-{video_id}{CAPTION_FILE_EXTENSION}'):
                self.logger.info(f"Successfully downloaded captions to {file}")
                return file

            log_warning_by_video_id(self.logger, video_id, "Caption download was attempted but no VTT file was found.")
            return None
        except Exception as e:
            self.logger.error(f"An error occurred while downloading captions for {video_id}: {e}")
            return None