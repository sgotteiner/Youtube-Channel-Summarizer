"""
Audio Extraction Service - Extracts audio from video files using the service framework.
"""
import datetime
from pathlib import Path
from src.pipeline.AudioExtractor import AudioExtractor
from src.utils.file_manager import FileManager
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.utils.postgresql_client import VideoStatus


class AudioExtractionService(ServiceTemplate[Path]):
    def __init__(self):
        super().__init__("audio_extraction")
        self.audio_extractor = AudioExtractor(self.logger)

    async def execute_pipeline(self, video, video_id: str) -> Path:
        # Check if working file path is available (contains the video file path for audio extraction)
        if not video.working_file_path:
            self.logger.error("[%s] Working file path not available in database", video_id)
            return None

        # Set up file paths
        file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=self.logger)
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        audio_path = video_paths["audio"]

        # Extract audio using the pipeline tool (automatically logs status)
        success = self.audio_extractor.extract_audio(Path(video.working_file_path), audio_path, video_id)

        if success:
            return audio_path
        else:
            return None

    async def get_working_file_path(self, video_id: str, video, result: Path) -> str:
        """
        Return the path of the extracted audio file to be saved as the working_file_path.
        """
        return str(result) if result else None

    async def get_service_specific_updates(self, video_id: str, video, result: Path) -> dict:
        """
        The audio extraction service doesn't need specific updates since working_file_path handles this.
        """
        return {}  # Audio extraction service relies on the working_file_path mechanism

    def build_event_payload(self, video_id: str, video, result: Path) -> dict:
        return {
            "video_id": video_id,
            "job_id": video.job_id,
            "extracted_at": datetime.datetime.utcnow().isoformat(),
            "audio_file_path": str(result)
        }


if __name__ == "__main__":
    # Create and run the service
    service = AudioExtractionService()
    service.run()