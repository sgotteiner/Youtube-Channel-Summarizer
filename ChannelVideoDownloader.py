"""
Module for downloading YouTube videos and channels.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging
from pytubefix import YouTube
from yt_dlp import YoutubeDL

class VideoDownloader:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _sanitize_filename(self, filename: str) -> str:
        sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
        return sanitized[:100]

    def download_video(self, youtube_video_url: str, video_title: str, upload_date: str, path_to_save_video: Path) -> Optional[Path]:
        """Download the video from YouTube."""
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
    def __init__(self, channel_name: str, num_videos: int = 1, max_length: Optional[int] = None, logger: Optional[logging.Logger] = None):
        self.channel_name = channel_name
        self.num_videos = num_videos
        self.max_length = max_length
        self.logger = logger
        self.video_data = self._get_video_metadata()

    def _get_channel_url(self) -> str:
        if not self.channel_name.startswith("http"):
            return f"https://www.youtube.com/{'@' if self.channel_name.startswith('@') else 'c/'}{self.channel_name.lstrip('@')}"
        return self.channel_name

    def _get_video_entries(self, channel_url: str) -> List[Dict]:
        ydl_opts = {"quiet": True, "extract_flat": True, "dump_single_json": True}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                channel_info = ydl.extract_info(channel_url, download=False)
                channel_id = channel_info.get("channel_id") or channel_info.get("id")
                if channel_id and channel_id.startswith("UC"):
                    uploads_playlist = f"UU{channel_id[2:]}"
                    playlist_url = f"https://www.youtube.com/playlist?list={uploads_playlist}"
                    playlist_info = ydl.extract_info(playlist_url, download=False)
                    return playlist_info.get("entries", [])
                
                videos_page = ydl.extract_info(f"{channel_url}/videos", download=False)
                return videos_page.get("entries", [])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Could not retrieve video entries for {channel_url}: {e}")
            return []

    def _fetch_full_metadata(self, video_entries: List[Dict]) -> List[Dict]:
        all_videos = []
        ydl_opts = {"quiet": True, "skip_download": True}
        with YoutubeDL(ydl_opts) as ydl:
            for entry in video_entries:
                if not entry or not entry.get("id"):
                    continue
                try:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={entry['id']}", download=False)
                    all_videos.append(self._parse_video_info(info))
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to fetch info for video ID {entry['id']}: {e}")
        return all_videos

    def _parse_video_info(self, info: Dict) -> Dict:
        upload_date_raw = info.get("upload_date", "")
        formatted_date = f"{upload_date_raw[6:8]}_{upload_date_raw[4:6]}_{upload_date_raw[0:4]}" if len(upload_date_raw) == 8 else ""
        
        manual_subs = info.get("subtitles", {{}})
        auto_subs = info.get("automatic_captions", {{}})
        has_captions = any("en" in subs for subs in (manual_subs, auto_subs)) or \
                       any(k.startswith("en") for k in manual_subs.keys()) or \
                       any(k.startswith("en") for k in auto_subs.keys())

        return {
            "video_url": info.get("webpage_url"), "video_id": info.get("id"),
            "video_title": info.get("title", "Unknown Title"), "duration": info.get("duration"),
            "upload_date": formatted_date, "has_captions": has_captions
        }

    def _filter_and_prioritize_videos(self, all_videos: List[Dict]) -> List[Dict]:
        captioned = [v for v in all_videos if v["has_captions"]]
        non_captioned = [v for v in all_videos if not v["has_captions"] and self._is_valid_length(v)]
        
        combined = captioned + non_captioned
        return combined[:self.num_videos]

    def _is_valid_length(self, video: Dict) -> bool:
        if self.max_length is None:
            return True
        duration = video.get("duration")
        if duration is None:
            if self.logger:
                self.logger.warning(f"Could not get duration for video {video['video_title']}. Skipping length check.")
            return False
        return (duration / 60.0) <= float(self.max_length)

    def _get_video_metadata(self) -> List[Dict]:
        channel_url = self._get_channel_url()
        video_entries = self._get_video_entries(channel_url)
        all_videos_meta = self._fetch_full_metadata(video_entries)
        return self._filter_and_prioritize_videos(all_videos_meta)