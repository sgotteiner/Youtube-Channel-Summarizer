"""
Download Service - Downloads video files using the service framework.
"""
import datetime
from src.pipeline.VideoDownloader import VideoDownloader
from src.utils.file_manager import FileManager
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.utils.postgresql_client import VideoStatus


class DownloadService(ServiceTemplate[str]):
    def __init__(self):
        super().__init__("download")
        self.video_downloader = VideoDownloader(self.logger)

    async def execute_pipeline(self, video, video_id: str) -> str:
        # Set up file paths
        file_manager = FileManager(channel_name=video.channel_name, is_openai_runtime=False, logger=self.logger)
        video_data = {"video_title": video.title, "upload_date": video.upload_date, "video_id": video.id}
        video_paths = file_manager.get_video_paths(video_data)
        path_to_save_video = video_paths["video"].parent
        youtube_video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Download the video using the pipeline tool (automatically logs status)
        downloaded_path = self.video_downloader.download_video(
            youtube_video_url, video.title, video.upload_date, video_id, path_to_save_video
        )

        return str(downloaded_path) if downloaded_path else None

    async def get_working_file_path(self, video_id: str, video, result: str) -> str:
        """
        Return the path of the downloaded video file to be saved as the working_file_path.
        """
        return result

    async def get_service_specific_updates(self, video_id: str, video, result: str) -> dict:
        """
        The download service doesn't need specific updates since working_file_path handles this.
        """
        return {}  # Download service relies on the working_file_path mechanism

    def build_event_payload(self, video_id: str, video, result: str) -> dict:
        return {
            "video_id": video_id,
            "job_id": video.job_id,
            "downloaded_at": datetime.datetime.utcnow().isoformat(),
            "file_path": result
        }


if __name__ == "__main__":
    # Create and run the service
    service = DownloadService()
    service.run()