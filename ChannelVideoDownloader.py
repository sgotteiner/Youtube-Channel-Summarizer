"""
Module for downloading YouTube videos and fetching channel metadata.

This module contains two main classes:
-   VideoDownloader: Handles the downloading of a single YouTube video.
-   ChannelVideosDownloader: Fetches metadata for a specified number of videos
    from a YouTube channel efficiently.
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
    Fetches video metadata from a YouTube channel efficiently.
    It processes videos one by one, stopping when the desired number is reached.
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
        self.video_data = self._get_video_metadata_efficiently()

    def _get_channel_url(self) -> str:
        """Converts a channel name or handle into a full YouTube channel URL."""
        if not self.channel_name.startswith("http"):
            prefix = '@' if self.channel_name.startswith('@') else 'c/'
            channel_identifier = self.channel_name.lstrip('@')
            return f"https://www.youtube.com/{prefix}{channel_identifier}"
        return self.channel_name

    def _get_video_entries(self, channel_url: str) -> List[Dict]:
        """
        Retrieves a list of video entries (basic metadata) from the channel.
        This is a fast operation that does not fetch full details for each video.
        """
        self.logger.info(f"Fetching list of video entries for channel: {channel_url}")
        ydl_opts = {"quiet": True, "extract_flat": True, "dump_single_json": True}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                channel_info = ydl.extract_info(channel_url, download=False)
                channel_id = channel_info.get("channel_id") or channel_info.get("id")
                
                if channel_id and channel_id.startswith("UC"):
                    uploads_playlist_id = f"UU{channel_id[2:]}"
                    playlist_url = f"https://www.youtube.com/playlist?list={uploads_playlist_id}"
                    playlist_info = ydl.extract_info(playlist_url, download=False)
                    return playlist_info.get("entries", [])
                
                videos_page = ydl.extract_info(f"{channel_url}/videos", download=False)
                return videos_page.get("entries", [])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Could not retrieve video entries for {channel_url}: {e}")
            return []

    def _parse_video_info(self, info: Dict) -> Dict:
        """Parses the raw metadata dictionary from yt-dlp into a cleaner format."""
        upload_date_raw = info.get("upload_date", "")
        formatted_date = (
            f"{upload_date_raw[6:8]}_{upload_date_raw[4:6]}_{upload_date_raw[0:4]}"
            if len(upload_date_raw) == 8 else ""
        )

        # One-liner normalization: dict stays dict, list of dicts → merged dict, else {}
        normalize_info_dicts = lambda subs: subs if isinstance(subs, dict) else {k: v for d in subs for k, v in d.items()} if isinstance(subs, list) else {}

        manual_subs = normalize_info_dicts(info.get("subtitles"))
        auto_subs = normalize_info_dicts(info.get("automatic_captions"))

        has_captions = (
            any(k == "en" or k.startswith("en") for k in manual_subs.keys()) or
            any(k == "en" or k.startswith("en") for k in auto_subs.keys())
        )

        return {
            "video_url": info.get("webpage_url"),
            "video_id": info.get("id"),
            "video_title": info.get("title", "Unknown Title"),
            "duration": info.get("duration"),
            "upload_date": formatted_date,
            "has_captions": has_captions,
        }

    def _is_valid_video(self, video_meta: Dict) -> bool:
        """
        Checks if a video meets the specified criteria (e.g., length).
        Videos with captions always pass. Videos without captions are checked against max_length.
        """
        if video_meta["has_captions"]:
            return True
        
        if self.max_length is None:
            return True
            
        duration = video_meta.get("duration")
        if duration is None:
            if self.logger:
                self.logger.warning(f"Could not determine duration for '{video_meta['video_title']}'. Skipping.")
            return False

        is_within_length = (duration / 60.0) <= float(self.max_length)
        if not is_within_length:
            if self.logger:
                self.logger.info(f"Skipping video '{video_meta['video_title']}' (Length: {duration/60.0:.2f} min) as it exceeds max length and has no captions.")
        return is_within_length

    def _get_video_metadata_efficiently(self) -> List[Dict]:
        """
        Fetches metadata for videos one by one and stops when the desired number
        of valid videos is found. This is much more efficient than fetching all videos first.
        """
        channel_url = self._get_channel_url()
        video_entries = self._get_video_entries(channel_url)
        if not video_entries:
            return []

        self.logger.info(f"Found {len(video_entries)} total videos. Processing one by one to find {self.num_videos} valid videos...")
        
        valid_videos = []
        ydl_opts = {"quiet": True, "skip_download": True}
        with YoutubeDL(ydl_opts) as ydl:
            for i, entry in enumerate(video_entries):
                if not entry or not entry.get("id"):
                    continue

                video_id = entry['id']
                self.logger.info(f"Processing video {i+1}/{len(video_entries)} (ID: {video_id})...")

                try:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    video_meta = self._parse_video_info(info)
                    
                    if self._is_valid_video(video_meta):
                        self.logger.info(f"Found valid video: '{video_meta['video_title']}'")
                        valid_videos.append(video_meta)

                except Exception as e:
                    # This handles the 'unhashable type' error by logging it and continuing.
                    # This is likely an issue with yt-dlp for a specific video, not a fatal error.
                    if self.logger:
                        self.logger.warning(f"Failed to fetch full metadata for video ID {video_id}: {e}. Skipping video.")
                    continue

                # Stop once we have found enough videos.
                if len(valid_videos) >= self.num_videos:
                    self.logger.info(f"Found the desired number of {self.num_videos} valid videos. Stopping search.")
                    break
        
        return valid_videos