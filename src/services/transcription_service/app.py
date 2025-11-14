"""
Transcription Service - Transcribes audio files using the service framework.
"""
import datetime
from pathlib import Path
from src.pipeline.AudioTranscriber import AudioTranscriber
from src.utils.file_manager import FileManager
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.utils.postgresql_client import VideoStatus
import aiofiles


class TranscriptionService(ServiceTemplate[str]):
    def __init__(self):
        super().__init__("transcription")
        self.audio_transcriber = AudioTranscriber(self.logger)

    async def execute_pipeline(self, video, video_id: str) -> str:
        # Check if working file path is available (contains the audio file path for transcription)
        if not video.working_file_path:
            self.logger.error("[%s] Working file path not available in database", video_id)
            return None

        # Get the audio path from working_file_path
        audio_path = Path(video.working_file_path)
        
        # Transcribe the audio using the pipeline tool (automatically logs status)
        transcription_text = await self.audio_transcriber.transcribe_audio(audio_path, video_id=video_id)

        # Save transcription to the shared filesystem for the summarization service to access
        file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=self.logger)
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        transcription_path = video_paths["transcription"]

        # Create the directory if it doesn't exist and save the transcription to filesystem
        transcription_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(transcription_path, "w", encoding="utf-8") as f:
            await f.write(transcription_text or "")

        return transcription_text

    async def get_working_file_path(self, video_id: str, video, result: str) -> str:
        """
        Return the path of the transcription file to be saved as the working_file_path.
        """
        # Get the transcription file path based on video info
        file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=self.logger)
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        transcription_path = video_paths["transcription"]
        return str(transcription_path)

    async def get_service_specific_updates(self, video_id: str, video, result: str) -> dict:
        """
        Transcription service doesn't set audio_file_path or video_file_path since it creates a transcription file.
        """
        return {}  # Transcription doesn't update the main file path fields

    def build_event_payload(self, video_id: str, video, result: str) -> dict:
        return {
            "video_id": video_id,
            "job_id": video.job_id,
            "transcribed_at": datetime.datetime.utcnow().isoformat(),
            "character_count": len(result)
        }


if __name__ == "__main__":
    # Create and run the service
    service = TranscriptionService()
    service.run()