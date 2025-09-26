"""
Module for fetching video metadata from YouTube.
"""
from typing import List, Dict, Optional
import logging
from yt_dlp import YoutubeDL

class VideoMetadataFetcher:
    """Fetches video metadata from a YouTube channel efficiently."""
    def __init__(self, channel_id: str, logger: Optional[logging.Logger] = None):
        self.channel_id = channel_id
        self.logger = logger

    def _get_channel_url(self) -> str:
        """Constructs the full YouTube channel URL from a channel ID."""
        return f"https://www.youtube.com/channel/{self.channel_id}"

    def get_video_entries(self) -> List[Dict]:
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

    def fetch_video_details(self, video_id: str) -> Optional[Dict]:
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
