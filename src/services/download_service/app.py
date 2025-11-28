"""
Download Service - Downloads audio files using the service framework.
"""
from src.pipeline.VideoDownloader import AudioDownloader
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.enums.service_enums import ServiceType


class DownloadService(ServiceTemplate[str]):
    def __init__(self):
        super().__init__(ServiceType.DOWNLOAD)
        self.audio_downloader = AudioDownloader(self.logger)

    def get_input_file_path(self, video_paths):
        """
        Download service doesn't need an input file path (it downloads from URL).
        """
        return None  # No input file needed for download service

    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str) -> str:
        # Download service doesn't use input file path, just needs video_paths for output location
        path_to_save_audio = video_paths["audio"].parent  # Use audio path instead of video path
        youtube_video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Download the audio using the pipeline tool (automatically logs status)
        downloaded_path = self.audio_downloader.download_audio(
            youtube_video_url, video.title, video.upload_date, video_id, path_to_save_audio
        )

        return str(downloaded_path) if downloaded_path else None

    def get_service_specific_event_fields(self, video_id: str, video, result: str) -> dict:
        return {
            "file_path": result
        }


if __name__ == "__main__":
    # Create and run the service
    service = DownloadService()
    service.run()