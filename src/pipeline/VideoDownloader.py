"""
Module for downloading YouTube videos and captions.
"""
from pathlib import Path
from typing import Optional
import logging
from pytubefix import YouTube
from yt_dlp import YoutubeDL
from src.utils.common_logger import log_success_by_video_id, log_error_by_video_id, log_warning_by_video_id, sanitize_filename
from src.constants.service_constants import VIDEO_FILE_EXTENSION, CAPTION_FILE_EXTENSION


class VideoDownloader:
    """Handles the downloading of a single YouTube video and its captions."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger


    def _check_file_exists_and_log(self, video_filepath: Path, video_title: str, video_id: str) -> Optional[Path]:
        """Check if the video file already exists and log appropriately."""
        if video_filepath.exists():
            self.logger.info(f"Video '{video_title}' already exists. Skipping download.")
            # Log the completion status with video_id format too
            log_success_by_video_id(self.logger, video_id, "Video downloaded successfully to: %s", video_filepath)
            return video_filepath
        return None

    def _get_youtube_stream(self, youtube_video_url: str) -> Optional:
        """Get the YouTube video stream."""
        try:
            yt = YouTube(youtube_video_url)
            video = yt.streams.filter(file_extension='mp4', progressive=True).first()
            return video
        except Exception as e:
            self.logger.error(f'Error accessing YouTube video {youtube_video_url}: {e}')
            return None

    def _download_stream(self, video_stream, path_to_save_video: Path, sanitized_filename: str) -> bool:
        """Download the YouTube video stream to the specified location."""
        try:
            self.logger.info(f"Downloading video to {path_to_save_video / sanitized_filename}...")
            video_stream.download(output_path=str(path_to_save_video), filename=sanitized_filename)
            self.logger.info("Download successful.")
            return True
        except Exception as e:
            self.logger.error(f'Error downloading video: {e}')
            return False

    def download_video(self, youtube_video_url: str, video_title: str, upload_date: str, video_id: str, path_to_save_video: Path) -> Optional[Path]:
        """
        Downloads a single video from a given YouTube URL using the name-date-id format.

        Args:
            youtube_video_url (str): The YouTube URL to download from
            video_title (str): Title of the video
            upload_date (str): Upload date of the video
            video_id (str): The video ID for logging purposes
            path_to_save_video (Path): Path where the video will be saved

        Returns:
            Optional[Path]: Path to the downloaded video, or None if failed
        """
        sanitized_filename = f"{sanitize_filename(video_title)}-{upload_date}-{video_id}{VIDEO_FILE_EXTENSION}"
        video_filepath = path_to_save_video / sanitized_filename

        # Check if file already exists
        existing_file = self._check_file_exists_and_log(video_filepath, video_title, video_id)
        if existing_file:
            return existing_file

        # Get the YouTube video stream
        video = self._get_youtube_stream(youtube_video_url)
        if not video:
            log_error_by_video_id(self.logger, video_id, "No suitable MP4 stream found. Failed to download video")
            return None

        # Download the video
        success = self._download_stream(video, path_to_save_video, sanitized_filename)

        if success:
            # Log the completion status with video_id format
            log_success_by_video_id(self.logger, video_id, "Video downloaded successfully to: %s", video_filepath)
            return video_filepath
        else:
            # Log the failure with video_id format
            log_error_by_video_id(self.logger, video_id, "Failed to download video")
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