"""
Module for downloading YouTube videos and fetching channel metadata.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging
from pytubefix import YouTube
from yt_dlp import YoutubeDL
from FileManager import FileManager

class VideoDownloader:
    """Handles the downloading of a single YouTube video."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _sanitize_filename(self, filename: str) -> str:
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

class ChannelVideosDownloader:
    """Fetches video metadata from a YouTube channel efficiently."""
    def __init__(self, channel_name: str, logger: Optional[logging.Logger] = None):
        self.channel_name = channel_name
        self.logger = logger

    def _get_channel_url(self) -> str:
        """Converts a channel name or handle into a full YouTube channel URL."""
        if not self.channel_name.startswith("http"):
            prefix = '@' if self.channel_name.startswith('@') else 'c/'
            return f"https://www.youtube.com/{prefix}{self.channel_name.lstrip('@')}"
        return self.channel_name

    def _get_video_entries(self) -> List[Dict]:
        """
        Retrieves a fast, lightweight list of video entries from the channel.
        """
        self.logger.info(f"Fetching lightweight list of video entries for '{self.channel_name}'...")
        channel_url = self._get_channel_url()
        ydl_opts = {"quiet": True, "extract_flat": True, "dump_single_json": True}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(f"{channel_url}/videos", download=False)
                entries = playlist_info.get("entries", [])
                self.logger.info(f"Found {len(entries)} video entries.")
                return entries
        except Exception as e:
            self.logger.error(f"Could not retrieve video entries for {channel_url}: {e}")
            return []

    # NO AI EDITS
    def _parse_video_info(self, info: Dict) -> Dict:
        """Parses the raw metadata dictionary from yt-dlp into a cleaner format."""
        upload_date_raw = info.get("upload_date", "")
        formatted_date = f"{upload_date_raw[6:8]}_{upload_date_raw[4:6]}_{upload_date_raw[0:4]}" if len(upload_date_raw) == 8 else ""
        
        subtitles = info.get("subtitles", {})
        automatic_captions = info.get("automatic_captions", {})
        
        has_captions = False
        if subtitles:
            en_subtitles = subtitles.get("en", [])
            if any(sub.get("ext") == "vtt" for sub in en_subtitles):
                has_captions = True
        
        if not has_captions and automatic_captions:
            en_auto_captions = automatic_captions.get("en", [])
            if any(cap.get("ext") == "vtt" for cap in en_auto_captions):
                has_captions = True

        return {
            "video_url": info.get("webpage_url"), "video_id": info.get("id"),
            "video_title": info.get("title", "Unknown Title"), "duration": info.get("duration"),
            "upload_date": formatted_date, "has_captions": has_captions
        }

    def _fetch_video_details(self, video_id: str) -> Optional[Dict]:
        """
        Fetches the full, detailed metadata for a single video.
        """
        self.logger.debug(f"Fetching full metadata for video ID: {video_id}...")
        ydl_opts = {"quiet": True, "skip_download": True}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return self._parse_video_info(info)
        except Exception as e:
            self.logger.warning(f"Failed to fetch metadata for video ID {video_id}: {e}")
            return None

    def _is_video_valid(self, video_details: Dict, max_length: Optional[int], apply_max_length_for_captionless_only: bool) -> bool:
        """
        Checks if a video with full details is valid for processing based on length and caption availability.
        """
        duration = video_details.get("duration")
        if duration is None:
            self.logger.warning(f"Could not determine duration for '{video_details['video_title']}'. Skipping.")
            return False

        if max_length is None:
            return True

        is_too_long = (duration / 60.0) > float(max_length)

        if is_too_long:
            if apply_max_length_for_captionless_only and video_details["has_captions"]:
                self.logger.info(f"Video '{video_details['video_title']}' exceeds length limit, but has captions. It is valid.")
                return True
            
            self.logger.info(f"Skipping video '{video_details['video_title']}' (Length: {duration/60.0:.2f} min) as it exceeds the {max_length} min limit.")
            return False
        
        return True

    def discover_videos(self, file_manager: FileManager, num_videos_to_process: Optional[int], max_video_length: Optional[int], apply_max_length_for_captionless_only: bool) -> List[Dict]:
        """
        Discovers new, valid videos to be processed.
        """
        self.logger.info("--- Starting video discovery phase ---")
        videos_to_process = []
        video_limit_text = "all available" if num_videos_to_process is None else str(num_videos_to_process)
        self.logger.info(f"Goal: Find {video_limit_text} videos from '{self.channel_name}' that have not been summarized yet.")

        video_entries = self._get_video_entries()
        for entry in video_entries:
            if file_manager.does_summary_exist(entry['id']):
                self.logger.info(f"Summary for '{entry['title']}' already exists. Skipping.")
                continue
            
            self.logger.info(f"Summary for '{entry['title']}' not found. Fetching full video details...")
            video_details = self._fetch_video_details(entry['id'])
            
            if not video_details:
                continue

            if self._is_video_valid(video_details, max_video_length, apply_max_length_for_captionless_only):
                self.logger.info(f"Video '{video_details['video_title']}' is valid. Adding to processing queue.")
                videos_to_process.append(video_details)
            
            if num_videos_to_process is not None and len(videos_to_process) >= num_videos_to_process:
                self.logger.info(f"Reached the limit of {num_videos_to_process} new videos to process.")
                break
        
        return videos_to_process
