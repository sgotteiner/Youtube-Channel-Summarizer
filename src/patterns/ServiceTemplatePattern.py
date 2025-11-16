"""
Framework for all services to handle common patterns: status updates, logging, messaging, etc.
"""
import abc
import logging
import datetime
from typing import Any, Dict, Optional, TypeVar, Generic
from src.utils.base_service import BaseService
from src.utils.postgresql_client import VideoStatus
from pathlib import Path


T = TypeVar('T')


class ServiceTemplate(Generic[T], BaseService, abc.ABC):
    """
    A framework that handles common service patterns like status updates, logging, and error handling.
    """
    def __init__(self, service_type: str):
        """
        Initialize the service framework with the service type.

        Args:
            service_type (str): The type of service (e.g., 'transcription', 'download', 'audio_extraction')
        """
        # Map service type to queue name
        queue_map = {
            'discovery': 'discovery_queue',
            'download': 'download_queue',
            'audio_extraction': 'audio_extraction_queue',
            'transcription': 'transcription_queue',
            'summarization': 'summarization_queue'
        }

        queue_name = queue_map.get(service_type, f"{service_type}_queue")
        super().__init__(queue_name)

        self.service_type = service_type
        self._setup_mappings()

    def _setup_mappings(self):
        """Set up mappings based on the service type."""
        # Map service type to status, queue, and event names
        self._status_map = {
            'discovery': {'in_progress': None, 'completion': None},  # Discovery is special
            'download': {'in_progress': VideoStatus.DOWNLOADING, 'completion': VideoStatus.DOWNLOADED},
            'audio_extraction': {'in_progress': VideoStatus.AUDIO_EXTRACTING, 'completion': VideoStatus.AUDIO_EXTRACTED},
            'transcription': {'in_progress': VideoStatus.TRANSCRIBING, 'completion': VideoStatus.TRANSCRIBED},
            'summarization': {'in_progress': VideoStatus.SUMMARIZING, 'completion': VideoStatus.COMPLETED}
        }

        self._next_queue_map = {
            'discovery': 'download_queue',
            'download': 'audio_extraction_queue',
            'audio_extraction': 'transcription_queue',
            'transcription': 'summarization_queue',
            'summarization': None  # Final step in pipeline
        }

        self._event_map = {
            'discovery': 'VideoDiscovered',
            'download': 'VideoDownloaded',
            'audio_extraction': 'AudioExtracted',
            'transcription': 'TranscriptionCompleted',
            'summarization': 'SummarizationCompleted'
        }

        self._name_map = {
            'discovery': 'video discovery',
            'download': 'video download',
            'audio_extraction': 'audio extraction',
            'transcription': 'audio transcription',
            'summarization': 'summarization'
        }

    def get_in_progress_status(self) -> Optional[VideoStatus]:
        """Return the VideoStatus to use when this service starts processing."""
        return self._status_map[self.service_type]['in_progress']

    def get_completion_status(self) -> VideoStatus:
        """Return the VideoStatus to use when this service completes successfully."""
        return self._status_map[self.service_type]['completion']

    def get_next_queue_name(self) -> str:
        """Return the name of the queue to send message to next in the pipeline."""
        return self._next_queue_map[self.service_type]

    def get_completion_event_name(self) -> str:
        """Return the name of the event to publish when this service completes."""
        return self._event_map[self.service_type]

    def get_task_name(self) -> str:
        """Return the name of the task for logging purposes."""
        return self._name_map[self.service_type]

    async def process_message(self, data: Dict[str, Any]) -> bool:
        """
        Main message processing framework.
        Handles the common pattern across all services.
        """
        # Store the original message data for services that need access to the full message
        self._original_message_data = data

        # For most services, get video_id from data, but for discovery service it might be job_id
        identifier = data.get("video_id", data.get("job_id", "unknown"))
        self.logger.info("[%s] Starting %s task", identifier, self.get_task_name())

        try:
            # Set video status to IN_PROGRESS status specific to this service only if video_id is present
            if "video_id" in data:
                in_progress_status = self.get_in_progress_status()
                if in_progress_status:
                    if not self.db_manager.update_video_status(data["video_id"], in_progress_status):
                        return False

            # Get the video record only if video_id is present
            video = None
            if "video_id" in data:
                video = self.db_manager.get_video(data["video_id"])
                if not video:
                    return False
            else:
                # For services that don't have video_id in their data (like discovery), pass None as video
                # The service needs to handle this appropriately in its execute_pipeline method
                pass

            # Execute the pipeline using the framework
            # Pass the appropriate identifier (video_id or job_id) to the execute_pipeline method
            actual_id = data.get("video_id", data.get("job_id", "unknown"))
            result = await self.execute_pipeline(video, actual_id)

            if result is not None:
                # Handle success - update status, send message, publish event
                # Only handle success with video_id if video_id is present in the original data
                if "video_id" in data:
                    return await self.handle_success(data["video_id"], video, result)
                else:
                    # For services like discovery that don't have video_id, just return True as success
                    # They'll handle their specific success logic in their execute_pipeline or overridden methods
                    return True
            else:
                # Handle failure - update status to FAILED
                return await self.handle_failure(actual_id)

        except Exception as e:
            self.logger.error("[%s] Error during %s: %s", identifier, self.get_task_name(), e)
            return await self.handle_failure(identifier)

    async def execute_pipeline(self, video, video_id: str) -> Optional[T]:
        """
        Execute the pipeline with standard file handling pattern.
        """
        # Setup file paths using video info
        file_manager = self.create_file_manager(video)
        video_data = self.prepare_video_data(video, video_id)
        video_paths = file_manager.get_video_paths(video_data)
        
        # Get input file path based on service-specific logic
        input_file_path = self.get_input_file_path(video_paths)
        
        # Validate input file exists if needed
        validated_input_path = None
        if input_file_path:
            validated_input_path = self.validate_input_file_path_internal(input_file_path, video_id)
            if not validated_input_path:
                return None
        
        # Call the specific operation implemented by each service
        return await self.perform_specific_operation(video, validated_input_path, video_paths, video_id)

    def get_input_file_path(self, video_paths):
        """
        Get the input file path for this service based on the video_paths dictionary.
        Override this method in services that need to validate an input file.
        By default, returns None (no input validation needed).
        """
        return None

    def validate_input_file_path_internal(self, input_file_path, video_id: str):
        """Internal method to validate that an input path exists."""
        if not input_file_path:
            self.logger.error("[%s] Input file path not available", video_id)
            return None

        if not input_file_path.exists():
            self.logger.error("[%s] Input file not found: %s", video_id, input_file_path)
            return None

        return input_file_path

    @abc.abstractmethod
    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str) -> Optional[T]:
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

    def create_file_manager(self, video):
        """Create a standardized FileManager instance for this service."""
        from src.utils.file_manager import FileManager
        return FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=self.logger)

    def prepare_video_data(self, video, video_id: str):
        """Prepare standardized video data dictionary for file operations."""
        return {
            "video_title": video.title,
            "upload_date": video.upload_date,
            "video_id": video_id
        }

    def validate_input_file_path(self, file_path: Path, video_id: str) -> Optional[Path]:
        """Validate that the specified file path exists and return it as Path object."""
        if not file_path:
            self.logger.error("[%s] File path is None", video_id)
            return None

        if not file_path.exists():
            self.logger.error("[%s] File does not exist: %s", video_id, file_path)
            return None

        return file_path

    async def handle_success(self, video_id: str, video, result: T) -> bool:
        """
        Handle successful pipeline execution for standard services (with video_id).
        """
        # Update status in the database
        updates = {"status": self.get_completion_status()}

        if not self.db_manager.update_video(video_id, **updates):
            return False

        # Send message to next service in the pipeline (if there is one)
        next_queue = self.get_next_queue_name()
        if next_queue:
            if not self.queue_manager.send_message(next_queue, {"video_id": video_id}, video_id):
                return False

        # Publish event for other services to consume
        event_payload = self.build_event_payload(video_id, video, result)
        self.event_manager.publish_event(self.get_completion_event_name(), event_payload, video_id)

        self.logger.info("[%s] %s task completed successfully", video_id, self.get_task_name())
        return True

    async def handle_failure(self, video_id: str) -> bool:
        """
        Handle failed pipeline execution.
        """
        self.db_manager.update_video_status(video_id, VideoStatus.FAILED)
        return False

    def build_event_payload(self, video_id: str, video, result: T) -> Dict[str, Any]:
        """
        Build the event payload to publish when this service completes.
        Calls get_service_specific_event_fields to get service-specific fields.
        """
        # Handle the case where video might be None (for discovery service)
        job_id = getattr(video, 'job_id', 'unknown') if video is not None else 'unknown'
        base_payload = {
            "video_id": video_id,
            "job_id": job_id,
            "completed_at": datetime.datetime.utcnow().isoformat()
        }
        
        # Get service-specific fields and merge them into the base payload
        service_specific_fields = self.get_service_specific_event_fields(video_id, video, result)
        base_payload.update(service_specific_fields)
        
        return base_payload

    def get_service_specific_event_fields(self, video_id: str, video, result: T) -> Dict[str, Any]:
        """
        Get service-specific fields to add to the event payload.
        Override this method in services that need to add specific fields.
        """
        # Default: no additional fields
        return {}