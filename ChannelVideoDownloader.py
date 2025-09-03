from pytubefix import YouTube
from yt_dlp import YoutubeDL
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
        self.download_video()

    def download_video(self):
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
    def __init__(self, channel_name, path_to_save_videos, max_results=1, logger=None):
        """
        This class finds the videos of a YouTube channel by its name and downloads them. It only downloads the first 30
        because that's what javascript loads before dynamically loading more when scrolling down. Getting all the videos
        is possible using the YouTube API. It is probably also possible using web scraping.

        :param channel_name: The most convenient way to use the URL. sometimes it works better with the channel ID.
        This code works using the channel name but in order to use channel ID the url is 'https://www.youtube.com/channel<channel ID>
        The channel ID can be found at the page source of the channel page searching for "channel_id=".
        """

        self.channel_name = channel_name
        self.max_results = max_results
        self.logger = logger

        self.video_urls = self.get_video_urls_from_channel_name(channel_name, max_results)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(lambda url: VideoDownloader(url, path_to_save_videos, self.logger), self.video_urls)

    def get_video_urls_from_channel_name(self, channel_name, max_results=1):
        if not channel_name.startswith("http"):
            channel_name = f"https://www.youtube.com/c/{channel_name}"

            ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "dump_single_json": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"{channel_name}/videos", download=False)
            video_urls = [f"https://www.youtube.com/watch?v={e['id']}" for e in info.get("entries", []) if e.get("id")]

        return video_urls[:max_results]