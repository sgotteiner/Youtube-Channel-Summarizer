"""
Discovery Service - Discovers new videos from a YouTube channel using the service framework.
"""
import datetime
from typing import Optional
from src.pipeline.VideoMetadataFetcher import VideoMetadataFetcher
from src.pipeline.VideoDiscoverer import VideoDiscoverer
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.enums.service_enums import ServiceType


class DiscoveryService(ServiceTemplate[dict]):
    def __init__(self):
        super().__init__(ServiceType.DISCOVERY)

    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str):
        """
        Discovery service doesn't use this method since it overrides execute_pipeline.
        This is a required implementation for the abstract method.
        """
        # This method is not used by Discovery service since it overrides execute_pipeline
        pass

    async def execute_pipeline(self, video, identifier: str) -> Optional[dict]:
        """
        Override execute_pipeline for discovery service since it operates differently from other services.
        The discovery service doesn't work on individual video files but discovers videos from a channel.
        The 'video' parameter is None for discovery service, and identifier relates to the job.
        """
        # For discovery service, we get the job parameters from the original message data
        data = getattr(self, '_original_message_data', {})
        job_id = data["job_id"]
        channel_name = data["channel_name"]
        num_videos_to_process = data.get("num_videos_to_process")
        max_video_length = data.get("max_video_length")
        apply_max_length_for_captionless_only = data.get("apply_max_length_for_captionless_only", False)

        # Set up the discovery tools
        metadata_fetcher = VideoMetadataFetcher(channel_name, logger=self.logger)
        video_discoverer = VideoDiscoverer(self.logger, metadata_fetcher, self.db_manager)

        # Discover videos that match our criteria
        discovered_videos = video_discoverer.discover_videos(
            channel_name, job_id, num_videos_to_process, 
            max_video_length, apply_max_length_for_captionless_only
        )

        # Process discovered videos - create records and send to next service
        processed_count = 0
        for video_details in discovered_videos:
            discovered_video_id = video_details['video_id']

            # Create video record in database
            if not self.db_manager.create_video_record(
                discovered_video_id, job_id, channel_name,
                video_details["video_title"], video_details["upload_date"],
                video_details.get("duration")
            ):
                continue  # Skip if creation failed

            # Send message to next service in the pipeline
            if not self.queue_manager.send_message(ServiceType.DOWNLOAD, {"video_id": discovered_video_id}, discovered_video_id):
                continue  # Skip if sending message failed

            processed_count += 1

        return {
            "success": True, 
            "videos_found": processed_count, 
            "job_id": job_id, 
            "channel_name": channel_name
        }

    def get_service_specific_event_fields(self, identifier: str, video, result: dict) -> dict:
        # For discovery service, we need to build event from the original message data
        data = getattr(self, '_original_message_data', {})
        return {
            "job_id": data.get("job_id"),
            "channel_name": data.get("channel_name"),
            "discovered_at": datetime.datetime.utcnow().isoformat(),
            "videos_found": result.get("videos_found", 0) if result else 0
        }


if __name__ == "__main__":
    # Create and run the service
    service = DiscoveryService()
    service.run()