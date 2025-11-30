"""
Download Service - Downloads audio or captions using the service framework.
"""
from src.pipeline.VideoDownloader import VideoDataDownloader
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.enums.service_enums import ServiceType
from src.enums.service_enums import ServiceType as ST


class DownloadService(ServiceTemplate[str]):
    def __init__(self):
        super().__init__(ServiceType.DOWNLOAD)
        self.data_downloader = VideoDataDownloader(self.logger)

    def get_input_file_path(self, video_paths):
        """
        Download service doesn't need an input file path (it downloads from URL).
        """
        return None  # No input file needed for download service

    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str) -> str:
        # Get the has_captions flag from the message data (sent by discovery service)
        data = getattr(self, '_original_message_data', {})
        has_captions = data.get('has_captions', False)

        # Initially set the next stage based on whether captions are expected to be available
        if has_captions:
            # If captions are expected to be available, initially assume next stage is summarization
            self.next_stage = ST.SUMMARIZATION
        else:
            # If no captions expected, next stage is transcription
            self.next_stage = ST.TRANSCRIPTION

        # Use the VideoDataDownloader to download either captions or audio
        result = await self.data_downloader.download(
            has_captions, video_id, video.title, video.upload_date, video_paths
        )

        # After download completes, check what was actually downloaded to determine the real next stage
        if result:
            from pathlib import Path
            result_path = Path(str(result))

            # If we expected captions but the result is an audio file, it means caption download failed
            # and we fell back to audio download - so route to transcription service
            if has_captions and result_path.suffix.lower() in ['.mp3', '.wav', '.m4a', '.aac', '.mp4']:
                self.next_stage = ST.TRANSCRIPTION  # Update next stage to transcription service

        return str(result) if result else None

    def get_service_specific_event_fields(self, video_id: str, video, result: str) -> dict:
        return {
            "file_path": result
        }


if __name__ == "__main__":
    # Create and run the service
    service = DownloadService()
    service.run()