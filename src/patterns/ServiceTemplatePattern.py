"""
Framework for all services to handle common patterns: status updates, logging, messaging, etc.
"""
import abc
from typing import Any, Dict, Optional, TypeVar, Generic
from src.utils.base_service import BaseService
from pathlib import Path
from src.utils.file_manager import FileManager
from src.enums.service_enums import ServiceType


T = TypeVar('T')


class ServiceTemplate(Generic[T], BaseService, abc.ABC):
    """
    A framework that handles common service patterns like status updates, logging, and error handling.
    """
    def __init__(self, service_type: ServiceType):
        """
        Initialize the service framework with the service type enum.

        Args:
            service_type_enum: The ServiceType enum value for this service
        """
        super().__init__(service_type.name)

        self.service_type = service_type
        # Initialize with a default FileManager (will be updated per operation)
        self.file_manager = FileManager(channel_name="default", is_openai_runtime=False, logger=self.logger)
        # Default next stage is the next enum value
        from src.enums.service_enums import ServiceType as ST
        self.next_stage = ST(service_type.value + 1) if service_type.value + 1 < len(ST) else None


    async def process_message(self, data: Dict[str, Any]) -> bool:
        """
        Main message processing framework.
        Handles the common pattern across all services.
        """
        self._original_message_data = data
        identifier = self._get_identifier_from_data(data)
        self.logger.info("[%s] Starting %s task", identifier, self.service_type.name)

        try:
            await self._update_status_if_needed(data)
            video = self._get_video_record(data)
            if video is False:  # Error occurred
                return False

            actual_id = data.get("video_id", data.get("job_id", "unknown"))
            result = await self.execute_pipeline(video, actual_id)

            if result is not None:
                return await self._handle_success_for_data(data, result)
            else:
                return await self.handle_failure(actual_id)

        except Exception as e:
            self.logger.error("[%s] Error during %s: %s", identifier, self.service_type.name, e)
            return await self.handle_failure(identifier)

    def _get_identifier_from_data(self, data: Dict[str, Any]) -> str:
        """Extract the identifier from message data."""
        return data.get("video_id", data.get("job_id", "unknown"))

    async def _update_status_if_needed(self, data: Dict[str, Any]) -> bool:
        """Update video status to IN_PROGRESS if video_id is present in data."""
        if "video_id" in data:
            from src.enums.service_enums import ProcessingStatus
            if not self.db_manager.update_video_stage_and_status(data["video_id"], self.service_type.name, ProcessingStatus.PROCESSING.value):
                return False
        return True

    def _get_video_record(self, data: Dict[str, Any]):
        """Get the video record if video_id is present in data."""
        if "video_id" in data:
            video = self.db_manager.get_video(data["video_id"])
            if not video:
                return False
            return video
        return None  # No video record needed for discovery service

    async def _handle_success_for_data(self, data: Dict[str, Any], result: T) -> bool:
        """Handle success scenario for message data with or without video_id."""
        if "video_id" in data:
            return await self.handle_success(data["video_id"], data.get("video", None), result)
        else:
            # For services like discovery that don't have video_id, just return True as success
            return True

    async def execute_pipeline(self, video, video_id: str) -> Optional[T]:
        """
        Execute the pipeline with standard file handling pattern.
        """
        # Update the file manager with the correct channel name
        if video and hasattr(video, 'channel_name'):
            self.file_manager.channel_name = video.channel_name
        else:
            self.file_manager.channel_name = "default"

        video_paths = self._get_video_paths(video, video_id)

        # Validate input file path if needed
        validated_input_path = None
        input_file_path = self.get_input_file_path(video_paths)
        if input_file_path:
            validated_input_path = self.file_manager.validate_input_file_path(input_file_path, video_id)

        return await self.perform_specific_operation(video, validated_input_path, video_paths, video_id)

    def _get_video_paths(self, video, video_id: str) -> Dict[str, Path]:
        """Get video paths using file manager."""
        video_data = self.prepare_video_data(video, video_id)
        return self.file_manager.get_video_paths(video_data)


    def get_input_file_path(self, video_paths):
        """
        Get the input file path for this service based on the video_paths dictionary.
        Override this method in services that need to validate an input file.
        By default, returns None (no input validation needed).
        """
        return None

    @abc.abstractmethod
    async def perform_specific_operation(self, video, input_file_path: Optional[Path],
                                       video_paths: Dict[str, Path], video_id: str) -> Optional[T]:
        """
        Perform the specific operation for this service.
        This must be implemented by each service.

        Args:
            video: The video object
            input_file_path: The validated input file path (or None)
            video_paths: Dictionary of video paths
            video_id: The video ID to process

        Returns:
            The result of the operation or None if failed
        """
        pass


    def prepare_video_data(self, video, video_id: str):
        """Prepare standardized video data dictionary for file operations."""
        video_title = getattr(video, 'title', 'unknown')
        upload_date = getattr(video, 'upload_date', 'unknown')
        return {
            "video_title": video_title,
            "upload_date": upload_date,
            "video_id": video_id
        }

    async def handle_success(self, video_id: str, video, result: T) -> bool:
        """
        Handle successful pipeline execution for standard services (with video_id).
        """
        # Use the service's configured next_stage
        from src.enums.service_enums import ProcessingStatus
        next_service_enum = self.next_stage

        if next_service_enum is not None:
            if not self.db_manager.update_video_stage_and_status(video_id, next_service_enum.name, ProcessingStatus.PROCESSING.value):
                return False

            # Send message to next service in the pipeline
            if not self.queue_manager.send_message(next_service_enum, {"video_id": video_id}, video_id):
                return False
        else:
            # This is the final service in the pipeline, mark as completed
            if not self.db_manager.update_video_stage_and_status(video_id, self.service_type.name, ProcessingStatus.COMPLETED.value):
                return False

        service_specific_fields = self.get_service_specific_event_fields(video_id, video, result)

        self.event_manager.publish_event(
            self.service_type.name,
            self.event_manager.build_event_payload(video_id, video, result, service_specific_fields),
            video_id
        )

        self.logger.info("[%s] %s task completed successfully", video_id, self.service_type.name)
        return True

    async def handle_failure(self, video_id: str) -> bool:
        """
        Handle failed pipeline execution.
        """
        from src.enums.service_enums import ProcessingStatus
        self.db_manager.update_video_stage_and_status(video_id, self.service_type.name, ProcessingStatus.FAILED.value)
        return False

    def get_service_specific_event_fields(self, video_id: str, video, result: T) -> Dict[str, Any]:
        """
        Get service-specific fields to add to the event payload.
        Override this method in services that need to add specific fields.
        """
        # Default: no additional fields
        return {}