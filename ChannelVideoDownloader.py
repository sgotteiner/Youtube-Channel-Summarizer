"""
Module for downloading YouTube videos and channels.
"""

from pytubefix import YouTube
from yt_dlp import YoutubeDL
from pathlib import Path
from typing import List, Dict
import logging
import re # Import re for sanitizing filenames

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(message)s')


class VideoDownloader:
    def __init__(self, logger):
        self.logger = logger

    def download_video(self, youtube_video_url: str, video_title: str, upload_date: str, path_to_save_video: Path) -> Path | None:
        """Download the video from YouTube."""
        try:
            yt = YouTube(youtube_video_url)
            video = yt.streams.filter(file_extension='mp4', progressive=True).first()
            if not video:
                self.logger.warning(f"No suitable MP4 stream found for {youtube_video_url}. Skipping download.")
                return None

            # Sanitize filename to prevent issues with special characters
            sanitized_video_title = re.sub(r'[\\/:*?"<>|]', '', video_title) # Remove invalid characters
            sanitized_video_title = sanitized_video_title[:100] # Truncate to avoid excessively long filenames
            sanitized_filename = f"{sanitized_video_title}-{upload_date}.mp4"
            video_filepath = path_to_save_video / sanitized_filename

            if video_filepath.exists():
                self.logger.info(f"Video '{video_title}' already exists at {video_filepath}. Skipping download.")
                return video_filepath

            self.logger.info(f"Starting download for '{video_title}' to {video_filepath}...")
            video.download(output_path=str(path_to_save_video), filename=sanitized_filename)
            self.logger.info(f"Download successful for '{video_title}'.")
            return video_filepath
        except Exception as e:
            self.logger.error(f'Error downloading {youtube_video_url}: {e}')
            return None


class ChannelVideosDownloader:
    def __init__(self, channel_name, num_videos_to_process=1, max_video_length=None, logger=None):
        """
        This class finds the videos of a YouTube channel by its name and retrieves their metadata.
        It does not download the videos.
        
        :param channel_name: Channel name or URL
        :param num_videos_to_process: Maximum number of videos to retrieve metadata for that meet the length criteria
        :param max_video_length: Maximum length of video in minutes. None for no limit.
        :param logger: Logger for logging messages
        """
        self.channel_name = channel_name
        self.num_videos_to_process = num_videos_to_process
        self.max_video_length = max_video_length
        self.logger = logger

        self.video_data = self.get_video_metadata_from_channel(channel_name, num_videos_to_process, max_video_length)

    def get_video_metadata_from_channel(self, channel_name: str, num_videos_to_process: int = 1, max_video_length: int = None) -> List[Dict]:
        """
        Extract video metadata (URL, title, duration, caption availability) from a YouTube channel, filtering by length.

        :param channel_name: Channel name or URL
        :param num_videos_to_process: Maximum number of video metadata entries to return that meet the length criteria
        :param max_video_length: Maximum length of video in minutes. None for no limit.
        :return: List of dictionaries, each containing 'video_url', 'video_title', 'video_id', 'duration', and 'has_captions'
        """
        # keep a safe logger reference
        logger = getattr(self, "logger", None)

        # Normalize channel input to a URL (support handles, /c/, or full URL)
        if not channel_name.startswith("http"):
            if channel_name.startswith("@"):
                channel_url = f"https://www.youtube.com/{channel_name}"
            else:
                channel_url = f"https://www.youtube.com/c/{channel_name}"
        else:
            channel_url = channel_name

        try:
            # First, try to quickly get a list of video IDs via the uploads playlist or /videos page
            ydl_opts_listing = {
                "quiet": True,
                "extract_flat": True,       # list entries only (fast)
                "dump_single_json": True,
            }

            with YoutubeDL(ydl_opts_listing) as ydl:
                # Try to get channel metadata to build uploads playlist (most reliable)
                try:
                    channel_info = ydl.extract_info(channel_url, download=False)
                except Exception:
                    channel_info = None

                channel_id = None
                if channel_info:
                    # common keys that can contain the channel id (e.g. 'UCxxxxx')
                    channel_id = channel_info.get("channel_id") or channel_info.get("id")

                entries = []
                if channel_id and isinstance(channel_id, str) and channel_id.startswith("UC"):
                    # Construct uploads playlist id = 'UU' + channel_id[2:]
                    uploads_playlist = f"UU{channel_id[2:]}"
                    playlist_url = f"https://www.youtube.com/playlist?list={uploads_playlist}"
                    try:
                        playlist_info = ydl.extract_info(playlist_url, download=False)
                        entries = playlist_info.get("entries", []) or []
                    except Exception:
                        entries = []
                # Fallback: try the channel/videos page (sometimes works)
                if not entries:
                    try:
                        videos_page = ydl.extract_info(f"{channel_url}/videos", download=False)
                        entries = videos_page.get("entries", []) or []
                    except Exception:
                        entries = []

                # Keep only items that have an id
                all_video_entries = [e for e in entries if e and e.get("id")]

            # Now fetch full metadata per video (this gives duration, subtitles, automatic_captions)
            captioned_videos_found = []
            non_captioned_videos_found = []
            ydl_opts_video = {
                "quiet": True,
                "skip_download": True,
            }

            with YoutubeDL(ydl_opts_video) as ydl_video:
                for entry in all_video_entries:
                    video_id = entry.get("id")
                    if not video_id:
                        continue
                    video_url = f"https://www.youtube.com/watch?v={video_id}"

                    try:
                        info = ydl_video.extract_info(video_url, download=False)
                    except Exception as e:
                        if logger:
                            logger.warning(f"Failed to fetch info for {video_url}: {e}")
                        continue

                    video_title = info.get("title", "Unknown Title")
                    duration_seconds = info.get("duration")  # seconds or None
                    upload_date_raw = info.get("upload_date") # YYYYMMDD format
                    formatted_upload_date = ""
                    if upload_date_raw and len(upload_date_raw) == 8:
                        formatted_upload_date = f"{upload_date_raw[6:8]}_{upload_date_raw[4:6]}_{upload_date_raw[0:4]}"

                    has_captions = False
                    manual_subs = info.get("subtitles") or {}
                    auto_subs = info.get("automatic_captions") or {}

                    if "en" in manual_subs or any(k.startswith("en") for k in manual_subs.keys()):
                        has_captions = True
                        if logger:
                            logger.info(f"Manual captions found for video: {video_title} ({video_url})")
                    elif "en" in auto_subs or any(k.startswith("en") for k in auto_subs.keys()):
                        has_captions = True
                        if logger:
                            logger.info(f"Automatic captions found for video: {video_title} ({video_url})")
                    else:
                        if logger:
                            logger.info(f"No English captions found for video: {video_title} ({video_url})")
                    
                    video_metadata = {
                        "video_url": video_url,
                        "video_id": video_id,
                        "video_title": video_title,
                        "duration": duration_seconds,
                        "upload_date": formatted_upload_date,
                        "has_captions": has_captions
                    }

                    if has_captions:
                        captioned_videos_found.append(video_metadata)
                    else:
                        # Apply max_video_length only to non-captioned videos
                        if max_video_length is not None:
                            if duration_seconds is None:
                                if logger:
                                    logger.warning(f"Could not get duration for video {video_title} ({video_url}). Skipping due to max_video_length constraint (no captions).")
                                continue
                            duration_minutes = duration_seconds / 60.0
                            if duration_minutes > float(max_video_length):
                                if logger:
                                    logger.info(f"Skipping video {video_title} (Length: {duration_minutes:.2f} min) as it exceeds max_video_length ({max_video_length} min) and has no captions.")
                                continue
                        non_captioned_videos_found.append(video_metadata)

                    # Stop if we have enough videos in total
                    if len(captioned_videos_found) + len(non_captioned_videos_found) >= int(num_videos_to_process):
                        break

            # Combine and prioritize captioned videos
            filtered_video_data = []
            # Take all captioned videos up to the limit
            for video in captioned_videos_found:
                if len(filtered_video_data) < int(num_videos_to_process):
                    filtered_video_data.append(video)
                else:
                    break
            # Fill remaining slots with non-captioned videos
            for video in non_captioned_videos_found:
                if len(filtered_video_data) < int(num_videos_to_process):
                    filtered_video_data.append(video)
                else:
                    break
        
        except Exception as e:
            if logger:
                logger.error(f"Error extracting video metadata: {e}")
            filtered_video_data = []

        return filtered_video_data
