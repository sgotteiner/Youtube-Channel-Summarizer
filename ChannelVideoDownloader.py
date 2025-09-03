"""
Module for downloading YouTube videos and channels.
"""

from pytubefix import YouTube
from yt_dlp import YoutubeDL
<<<<<<< HEAD
from typing import List


class VideoDownloader:
    """Handles downloading of individual YouTube videos."""

    def __init__(self, youtube_video_url: str, path_to_save_video: str):
        """
        Initialize the VideoDownloader and start the download process.
        
        :param youtube_video_url: URL of the YouTube video to download
        :param path_to_save_video: Path where the video should be saved
        """
        self.youtube_video_url = youtube_video_url
        self.path_to_save = path_to_save_video
=======
from pathlib import Path
import concurrent.futures
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(message)s')


class VideoDownloader:
    def __init__(self, youtube_video_url, path_to_save_video, logger):
        self.youtube_video_url = youtube_video_url
        self.path_to_save = path_to_save_video  # Path to save the downloaded video
        self.logger = logger
>>>>>>> qwen-demo
        self.download_video()

    def download_video(self) -> None:
        """Download the video from YouTube."""
        try:
            yt = YouTube(self.youtube_video_url)
            video_title = yt.title
            self.logger.info(f"Starting download for '{video_title}'...")

            video = yt.streams.filter(file_extension='mp4', progressive=True).first()
            video_filepath = Path(self.path_to_save) / video.default_filename
            if video_filepath.exists():
                self.logger.info(f"Video '{video_title}' already exists. Skipping download.")
                return

            video.download(self.path_to_save)
            self.logger.info(f"Download successful for '{video_title}'.")
        except Exception as e:
            self.logger.error(f'Error downloading {self.youtube_video_url}: {e}')


class ChannelVideosDownloader:
<<<<<<< HEAD
    """Handles downloading of YouTube channel videos."""
=======
    def __init__(self, channel_name, path_to_save_videos, max_results=1, logger=None):
        """
        This class finds the videos of a YouTube channel by its name and downloads them. It only downloads the first 30
        because that's what javascript loads before dynamically loading more when scrolling down. Getting all the videos
        is possible using the YouTube API. It is probably also possible using web scraping.
>>>>>>> qwen-demo

    def __init__(self, channel_name: str, path_to_save_videos: str, max_results: int = 1):
        """
        Initialize the ChannelVideosDownloader and extract video URLs.
        
        :param channel_name: Channel name or URL
        :param path_to_save_videos: Path where videos should be saved
        :param max_results: Maximum number of videos to download
        """
        self.channel_name = channel_name
        self.max_results = max_results
<<<<<<< HEAD
        self.video_urls = self.get_video_urls_from_channel_name(channel_name, max_results)

        # TODO: Uncomment the following lines to actually download videos
        for url in self.video_urls:
            print(url)
        #     VideoDownloader(url, path_to_save_videos)
=======
        self.logger = logger

        self.video_urls = self.get_video_urls_from_channel_name(channel_name, max_results)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(lambda url: VideoDownloader(url, path_to_save_videos, self.logger), self.video_urls)
>>>>>>> qwen-demo

    def get_video_urls_from_channel_name(self, channel_name: str, max_results: int = 1) -> List[str]:
        """
        Extract video URLs from a YouTube channel.
        
        :param channel_name: Channel name or URL
        :param max_results: Maximum number of video URLs to return
        :return: List of video URLs
        """
        if not channel_name.startswith("http"):
            channel_name = f"https://www.youtube.com/c/{channel_name}"

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "dump_single_json": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"{channel_name}/videos", download=False)
                video_urls = [f"https://www.youtube.com/watch?v={e['id']}" for e in info.get("entries", []) if e.get("id")]
        except Exception as e:
            print(f"Error extracting video URLs: {e}")
            video_urls = []

        return video_urls[:max_results] 
