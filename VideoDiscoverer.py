"""
Module for discovering new YouTube videos to be processed.
"""
from typing import List, Dict, Optional
import logging
from FileManager import FileManager
from VideoMetadataFetcher import VideoMetadataFetcher

class VideoDiscoverer:
    """
    Discovers new, valid videos from a YouTube channel that are ready to be processed.
    """
    def __init__(self, logger: logging.Logger, metadata_fetcher: VideoMetadataFetcher, file_manager: FileManager):
        self.logger = logger
        self.metadata_fetcher = metadata_fetcher
        self.file_manager = file_manager

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

    def discover_videos(self, num_videos_to_process: Optional[int], max_video_length: Optional[int], apply_max_length_for_captionless_only: bool) -> List[Dict]:
        """
        Discovers new, valid videos to be processed.
        """
        self.logger.info("--- Starting video discovery phase ---")
        videos_to_process = []
        video_limit_text = "all available" if num_videos_to_process is None else str(num_videos_to_process)
        self.logger.info(f"Goal: Find {video_limit_text} videos from '{self.metadata_fetcher.channel_name}' that have not been summarized yet.")

        video_entries = self.metadata_fetcher.get_video_entries()
        for entry in video_entries:
            if self.file_manager.does_summary_exist(entry['id']):
                self.logger.info(f"Summary for '{entry['title']}' already exists. Skipping.")
                continue
            
            self.logger.info(f"Summary for '{entry['title']}' not found. Fetching full video details...")
            video_details = self.metadata_fetcher.fetch_video_details(entry['id'])
            
            if not video_details:
                continue

            if self._is_video_valid(video_details, max_video_length, apply_max_length_for_captionless_only):
                self.logger.info(f"Video '{video_details['video_title']}' is valid. Adding to processing queue.")
                videos_to_process.append(video_details)
            
            if num_videos_to_process is not None and len(videos_to_process) >= num_videos_to_process:
                self.logger.info(f"Reached the limit of {num_videos_to_process} new videos to process.")
                break
        
        return videos_to_process
