"""
Discovery Service - Discovers new videos from a YouTube channel using the service framework.
"""
import datetime
from typing import Optional
from src.pipeline.VideoMetadataFetcher import VideoMetadataFetcher
from src.patterns.ServiceTemplatePattern import ServiceTemplate


def _is_video_valid(video_details: dict, max_length: Optional[int],
                   apply_max_length_for_captionless_only: bool, logger) -> bool:
    """Check if a video meets the criteria to be processed."""
    duration = video_details.get("duration")
    if duration is None:
        logger.warning("Could not determine duration for '%s'. Skipping.", video_details['video_title'])
        return False

    if max_length is None:
        return True

    is_too_long = (duration / 60.0) > float(max_length)

    if is_too_long:
        if apply_max_length_for_captionless_only and video_details["has_captions"]:
            logger.info("Video '%s' exceeds length limit, but has captions. It is valid.", video_details['video_title'])
            return True

        logger.info("Skipping video '%s' (Length: %.2f min) as it exceeds the %s min limit.", video_details['video_title'], duration/60.0, max_length)
        return False

    return True


class DiscoveryService(ServiceTemplate[dict]):
    def __init__(self):
        super().__init__("discovery")

    async def execute_pipeline(self, video, video_id: str) -> dict:
        # Discovery is special as it's the first in the pipeline
        # It doesn't really have "pipeline execution" in the same way as other services
        # Instead, it processes the entire discovery logic
        return None

    async def get_working_file_path(self, video_id: str, video, result: dict) -> str:
        """
        Discovery service doesn't generate a working file path.
        """
        return None  # Discovery doesn't create a file to track

    async def process_message(self, data: dict) -> bool:
        """
        Override to handle discovery-specific logic.
        """
        job_id = data["job_id"]
        channel_name = data["channel_name"]
        num_videos_to_process = data.get("num_videos_to_process")
        max_video_length = data.get("max_video_length")
        apply_max_length_for_captionless_only = data.get("apply_max_length_for_captionless_only", False)

        self.logger.info("[Job: %s] Starting video discovery for channel: %s", job_id, channel_name)

        try:
            # Use the async helper by executing blocking operations in the thread pool
            metadata_fetcher = VideoMetadataFetcher(channel_name, logger=self.logger)

            # Get video entries (network I/O operation)
            video_entries = metadata_fetcher.get_video_entries()
            videos_to_process_count = 0

            for entry in video_entries:
                video_id = entry['id']

                # Check if video already exists in database
                existing_video = self.db_manager.get_video(video_id)
                if existing_video:
                    self.logger.info("[%s] Video already exists in database. Skipping.", video_id)
                    continue

                self.logger.info("[%s] New video found. Fetching full video details...", video_id)

                # Fetch video details (network I/O operation) - automatically logs status
                video_details = metadata_fetcher.fetch_video_details(video_id)

                if not video_details:
                    self.logger.warning("[%s] Could not fetch video details. Skipping.", video_id)
                    continue

                # Validate video against criteria
                if _is_video_valid(video_details, max_video_length,
                                 apply_max_length_for_captionless_only, self.logger):
                    # Create video record in database
                    if not self.db_manager.create_video_record(
                        video_id, job_id, channel_name,
                        video_details["video_title"], video_details["upload_date"],
                        video_details.get("duration")
                    ):
                        continue

                    # Publish to next queue BEFORE committing to database to ensure pipeline continues even if DB updates fail
                    if not self.queue_manager.send_message("download_queue", {"video_id": video_id}, video_id):
                        continue  # Skip this video and continue with the next one

                    # Publish events AFTER queue message is sent to ensure pipeline continues even if events fail
                    event_payload = {
                        "video_id": video_id,
                        "job_id": job_id,
                        "channel_name": channel_name,
                        "title": video_details["video_title"],
                        "discovered_at": datetime.datetime.utcnow().isoformat()
                    }

                    self.event_manager.publish_event("VideoDiscovered", event_payload, video_id)

                    videos_to_process_count += 1
                # Note: Invalid video logging is handled automatically in the fetch_video_details method

                # Check if we've reached the limit
                if num_videos_to_process is not None and videos_to_process_count >= num_videos_to_process:
                    self.logger.info("Reached the limit of %s new videos to process for job %s.", num_videos_to_process, job_id)
                    break

            self.logger.info("[Job: %s] Discovery for channel %s complete. Found %s new videos.", job_id, channel_name, videos_to_process_count)
            return True

        except Exception as e:
            self.logger.error("Error during video discovery for job %s, channel %s: %s", job_id, channel_name, e)
            return False


if __name__ == "__main__":
    # Create and run the service
    service = DiscoveryService()
    service.run()