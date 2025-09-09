"""
Module for downloading YouTube videos and fetching channel metadata.

This module contains two main classes:
-   VideoDownloader: Handles the downloading of a single YouTube video.
-   ChannelVideosDownloader: Fetches metadata for a specified number of videos
    from a YouTube channel.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging
from pytubefix import YouTube
from yt_dlp import YoutubeDL

class VideoDownloader:
    """
    A class to handle the downloading of a single YouTube video.
    """
    def __init__(self, logger: logging.Logger):
        """
        Initializes the VideoDownloader.

        Args:
            logger (logging.Logger): The logger instance for logging messages.
        """
        self.logger = logger

    def _sanitize_filename(self, filename: str) -> str:
        """Removes invalid characters from a string to make it a valid filename."""
        sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
        return sanitized[:100]  # Truncate to avoid overly long filenames

    def download_video(self, youtube_video_url: str, video_title: str, upload_date: str, path_to_save_video: Path) -> Optional[Path]:
        """
        Downloads a single video from a given YouTube URL.

        Checks if the video already exists before downloading.

        Args:
            youtube_video_url (str): The URL of the YouTube video.
            video_title (str): The title of the video.
            upload_date (str): The upload date of the video.
            path_to_save_video (Path): The directory where the video will be saved.

        Returns:
            Optional[Path]: The path to the downloaded video file, or None if download failed.
        """
        sanitized_filename = f"{self._sanitize_filename(video_title)}-{upload_date}.mp4"
        video_filepath = path_to_save_video / sanitized_filename

        if video_filepath.exists():
            self.logger.info(f"Video '{video_title}' already exists at {video_filepath}. Skipping download.")
            return video_filepath

        try:
            yt = YouTube(youtube_video_url)
            video = yt.streams.filter(file_extension='mp4', progressive=True).first()
            if not video:
                self.logger.warning(f"No suitable MP4 stream found for {youtube_video_url}. Skipping download.")
                return None

            self.logger.info(f"Starting download for '{video_title}' to {video_filepath}...")
            video.download(output_path=str(path_to_save_video), filename=sanitized_filename)
            self.logger.info(f"Download successful for '{video_title}'.")
            return video_filepath
        except Exception as e:
            self.logger.error(f'Error downloading {youtube_video_url}: {e}')
            return None

class ChannelVideosDownloader:
    """
    Fetches video metadata from a YouTube channel.
    It does not download the actual videos.
    """
    def __init__(self, channel_name: str, num_videos: int = 1, max_length: Optional[int] = None, logger: Optional[logging.Logger] = None):
        """
        Initializes the ChannelVideosDownloader.

        Args:
            channel_name (str): The name or URL of the YouTube channel.
            num_videos (int): The maximum number of videos to fetch metadata for.
            max_length (Optional[int]): The maximum video length in minutes. Videos exceeding this
                                        length will be skipped unless they have captions.
            logger (Optional[logging.Logger]): The logger instance.
        """
        self.channel_name = channel_name
        self.num_videos = num_videos
        self.max_length = max_length
        self.logger = logger
        self.video_data = self._get_video_metadata()

    def _get_channel_url(self) -> str:
        """Converts a channel name or handle into a full YouTube channel URL."""
        if not self.channel_name.startswith("http"):
            # Handle channel names starting with '@' (handles) vs. older custom URLs
            prefix = '@' if self.channel_name.startswith('@') else 'c/'
            channel_identifier = self.channel_name.lstrip('@')
            return f"https://www.youtube.com/{prefix}{channel_identifier}"
        return self.channel_name

    def _get_video_entries(self, channel_url: str) -> List[Dict]:
        """
        Retrieves a list of video entries (basic metadata) from the channel.
        It tries to use the channel's 'uploads' playlist, which is the most reliable method.
        """
        ydl_opts = {"quiet": True, "extract_flat": True, "dump_single_json": True}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                # First, get channel info to find the channel ID
                channel_info = ydl.extract_info(channel_url, download=False)
                channel_id = channel_info.get("channel_id") or channel_info.get("id")
                
                # If a valid channel ID is found, construct the uploads playlist URL
                if channel_id and channel_id.startswith("UC"):
                    uploads_playlist_id = f"UU{channel_id[2:]}"
                    playlist_url = f"https://www.youtube.com/playlist?list={uploads_playlist_id}"
                    playlist_info = ydl.extract_info(playlist_url, download=False)
                    return playlist_info.get("entries", [])
                
                # Fallback to the /videos page if the playlist method fails
                videos_page = ydl.extract_info(f"{channel_url}/videos", download=False)
                return videos_page.get("entries", [])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Could not retrieve video entries for {channel_url}: {e}")
            return []

    def _fetch_full_metadata(self, video_entries: List[Dict]) -> List[Dict]:
        """
        Fetches detailed metadata for each video entry.
        This is necessary to get information like duration and caption availability.
        """
        all_videos = []
        ydl_opts = {"quiet": True, "skip_download": True}
        with YoutubeDL(ydl_opts) as ydl:
            for entry in video_entries:
                if not entry or not entry.get("id"):
                    continue
                try:
                    # Fetch detailed info for each video by its ID
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={entry['id']}", download=False)
                    all_videos.append(self._parse_video_info(info))
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to fetch full metadata for video ID {entry['id']}: {e}")
        return all_videos

    def _parse_video_info(self, info: Dict) -> Dict:
        """Parses the raw metadata dictionary from yt-dlp into a cleaner format."""
        upload_date_raw = info.get("upload_date", "")
        formatted_date = f"{upload_date_raw[6:8]}_{upload_date_raw[4:6]}_{upload_date_raw[0:4]}" if len(upload_date_raw) == 8 else ""
        
        manual_subs = info.get("subtitles", {{}})
        auto_subs = info.get("automatic_captions", {{}})
        # Check for English captions (both manual and auto-generated)
        has_captions = any("en" in subs for subs in (manual_subs, auto_subs)) or \
                       any(k.startswith("en") for k in manual_subs.keys()) or \
                       any(k.startswith("en") for k in auto_subs.keys())

        return {
            "video_url": info.get("webpage_url"), "video_id": info.get("id"),
            "video_title": info.get("title", "Unknown Title"), "duration": info.get("duration"),
            "upload_date": formatted_date, "has_captions": has_captions
        }

    def _filter_and_prioritize_videos(self, all_videos: List[Dict]) -> List[Dict]:
        """
        Filters videos based on length and prioritizes videos with captions.
        """
        # Separate videos into captioned and non-captioned lists
        captioned = [v for v in all_videos if v["has_captions"]]
        # Filter non-captioned videos by the max_length constraint
        non_captioned = [v for v in all_videos if not v["has_captions"] and self._is_valid_length(v)]
        
        # Combine the lists, with captioned videos appearing first
        combined = captioned + non_captioned
        # Return the desired number of videos
        return combined[:self.num_videos]

    def _is_valid_length(self, video: Dict) -> bool:
        """Checks if a video's duration is within the configured max_length."""
        if self.max_length is None:
            return True  # No length limit
        duration = video.get("duration")
        if duration is None:
            if self.logger:
                self.logger.warning(f"Could not get duration for video '{video['video_title']}'. Skipping length check.")
            return False
        return (duration / 60.0) <= float(self.max_length)

    def _get_video_metadata(self) -> List[Dict]:
        """
        The main method to orchestrate the fetching of video metadata.
        """
        channel_url = self._get_channel_url()
        video_entries = self._get_video_entries(channel_url)
        all_videos_meta = self._fetch_full_metadata(video_entries)
        return self._filter_and_prioritize_videos(all_videos_meta)
