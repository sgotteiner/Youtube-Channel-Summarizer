"""
Module for discovering new YouTube videos to be processed (service architecture only).
"""
from typing import List, Dict, Optional
import logging

class VideoDiscoverer:
    """
    Discovers new, valid videos from a YouTube channel that are ready to be processed.
    Service architecture version - checks database for existing videos.
    """
    def __init__(self, logger: logging.Logger, metadata_fetcher, db_manager):
        self.logger = logger
        self.metadata_fetcher = metadata_fetcher
        self.db_manager = db_manager

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

    def discover_videos(self, channel_name: str, job_id: str, num_videos_to_process: Optional[int], 
                        max_video_length: Optional[int], apply_max_length_for_captionless_only: bool) -> List[Dict]:
        """
        Discovers new, valid videos to be processed for service architecture.
        Checks database for existing videos.
        """
        self.logger.info(f"[Job: {job_id}] Starting video discovery for channel: {channel_name}")
        valid_videos = []
        
        video_limit_text = "all available" if num_videos_to_process is None else str(num_videos_to_process)
        self.logger.info(f"[Job: {job_id}] Goal: Find {video_limit_text} videos from '{channel_name}' that are not yet in the database.")

        # Get video entries from the channel
        video_entries = self.metadata_fetcher.get_video_entries()

        for entry in video_entries:
            video_id = entry['id']
            
            # Check if video already exists in database (to prevent duplicate discovery)
            existing_video = self.db_manager.get_video(video_id)
            if existing_video:
                self.logger.info(f"[{video_id}] Video already exists in database. Skipping.")
                continue

            self.logger.info(f"[{video_id}] New video found. Fetching full video details...")
            video_details = self.metadata_fetcher.fetch_video_details(video_id)

            if not video_details:
                self.logger.warning(f"[{video_id}] Could not fetch video details. Skipping.")
                continue

            if self._is_video_valid(video_details, max_video_length, apply_max_length_for_captionless_only):
                has_captions = video_details.get("has_captions", False)
                if has_captions:
                    self.logger.info(f"[{video_id}] Video is valid and HAS CAPTIONS. Adding to discovery results.")
                else:
                    self.logger.info(f"[{video_id}] Video is valid and has NO CAPTIONS. Adding to discovery results.")
                # Add the job_id to the video details to pass to service
                video_details['job_id'] = job_id
                valid_videos.append(video_details)
            else:
                self.logger.info(f"[{video_id}] Video is invalid. Skipping.")

            if num_videos_to_process is not None and len(valid_videos) >= num_videos_to_process:
                self.logger.info(f"[Job: {job_id}] Reached the limit of {num_videos_to_process} new videos to process.")
                break

        self.logger.info(f"[Job: {job_id}] Discovery complete. Found {len(valid_videos)} new videos.")
        return valid_videos 
