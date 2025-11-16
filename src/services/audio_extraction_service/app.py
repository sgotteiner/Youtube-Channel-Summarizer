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

    def get_input_file_path(self, video_paths):
        """
        Audio extraction service needs the video file as input.
        """
        return video_paths["video"]  # Input is the video file

    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str) -> Path:
        # Audio extraction needs the input video file path and outputs to audio path
        video_path = input_file_path
        audio_path = video_paths["audio"]

        # Extract audio using the pipeline tool (automatically logs status)
        success = self.audio_extractor.extract_audio(video_path, audio_path, video_id)

        if success:
            return audio_path
        else:
            return None

    def get_service_specific_event_fields(self, video_id: str, video, result: Path) -> dict:
        return {
            "audio_file_path": str(result) if result else None
        }


if __name__ == "__main__":
    # Create and run the service
    service = AudioExtractionService()
    service.run()