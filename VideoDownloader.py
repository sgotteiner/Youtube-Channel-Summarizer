"""
Module for downloading YouTube videos and captions.
"""
import re
from pathlib import Path
from typing import Optional
import logging
from pytubefix import YouTube
from yt_dlp import YoutubeDL

class VideoDownloader:
    """Handles the downloading of a single YouTube video and its captions."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _sanitize_filename(self, filename: str) -> str:
        """Removes illegal characters from a filename."""
        sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
        return sanitized[:100]

    def download_video(self, youtube_video_url: str, video_title: str, upload_date: str, video_id: str, path_to_save_video: Path) -> Optional[Path]:
        """
        Downloads a single video from a given YouTube URL using the name-date-id format.
        """
        sanitized_filename = f"{self._sanitize_filename(video_title)}-{upload_date}-{video_id}.mp4"
        video_filepath = path_to_save_video / sanitized_filename

        if video_filepath.exists():
            self.logger.info(f"Video '{video_title}' already exists. Skipping download.")
            return video_filepath

        try:
            yt = YouTube(youtube_video_url)
            video = yt.streams.filter(file_extension='mp4', progressive=True).first()
            if not video:
                self.logger.warning(f"No suitable MP4 stream for {youtube_video_url}. Skipping.")
                return None

            self.logger.info(f"Downloading '{video_title}' to {video_filepath}...")
            video.download(output_path=str(path_to_save_video), filename=sanitized_filename)
            self.logger.info(f"Download successful for '{video_title}'.")
            return video_filepath
        except Exception as e:
            self.logger.error(f'Error downloading {youtube_video_url}: {e}')
            return None

    def download_captions(self, video_id: str, destination_path: Path) -> Optional[Path]:
        """
        Downloads the English captions for a video to the specified path.
        Returns the path to the downloaded .vtt file if successful, otherwise None.
        """
        self.logger.info(f"Attempting to download captions for video ID: {video_id}")
        
        # yt-dlp expects a path template without the extension
        outtmpl = destination_path / f'%(title)s-%(upload_date)s-%(id)s.%(ext)s'
        
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
            for file in destination_path.glob(f'*-{video_id}.en.vtt'):
                self.logger.info(f"Successfully downloaded captions to {file}")
                return file
            
            self.logger.warning(f"Caption download was attempted for {video_id}, but no VTT file was found.")
            return None
        except Exception as e:
            self.logger.error(f"An error occurred while downloading captions for {video_id}: {e}")
            return None
