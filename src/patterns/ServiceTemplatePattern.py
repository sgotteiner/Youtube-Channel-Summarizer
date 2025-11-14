"""
Framework for all services to handle common patterns: status updates, logging, messaging, etc.
"""
import abc
import logging
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
        video_id = data["video_id"]
        self.logger.info("[%s] Starting %s task", video_id, self.get_task_name())
        
        try:
            # Set video status to IN_PROGRESS status specific to this service
            in_progress_status = self.get_in_progress_status()
            if in_progress_status:
                if not self.db_manager.update_video_status(video_id, in_progress_status):
                    return False

            # Get the video record
            video = self.db_manager.get_video(video_id)
            if not video:
                return False

            # Execute the pipeline using the framework
            result = await self.execute_pipeline(video, video_id)
            
            if result is not None:
                # Handle success - update status, send message, publish event
                return await self.handle_success(video_id, video, result)
            else:
                # Handle failure - update status to FAILED
                return await self.handle_failure(video_id)

        except Exception as e:
            self.logger.error("[%s] Error during %s: %s", video_id, self.get_task_name(), e)
            return await self.handle_failure(video_id)

    @abc.abstractmethod
    async def execute_pipeline(self, video, video_id: str) -> Optional[T]:
        """
        Execute the specific pipeline for this service.
        Return None if the pipeline fails, otherwise return the result.
        """
        pass

    async def handle_success(self, video_id: str, video, result: T) -> bool:
        """
        Handle successful pipeline execution.
        """
        # Determine working file path to update in database
        working_file_path = await self.get_working_file_path(video_id, video, result)
        
        # Update status and working file path in the database
        updates = {"status": self.get_completion_status()}
        if working_file_path:
            updates["working_file_path"] = working_file_path
            
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

    async def get_working_file_path(self, video_id: str, video, result: T) -> Optional[str]:
        """
        Get the working file path to update in the database when completing successfully.
        Override this method in services that need to update the working_file_path.
        By default, returns None (no file path to update).
        """
        return None

    async def handle_failure(self, video_id: str) -> bool:
        """
        Handle failed pipeline execution.
        """
        self.db_manager.update_video_status(video_id, VideoStatus.FAILED)
        return False

    def build_event_payload(self, video_id: str, video, result: T) -> Dict[str, Any]:
        """
        Build the event payload to publish when this service completes.
        Override this method to customize event payload.
        """
        return {
            "video_id": video_id,
            "job_id": video.job_id
        }