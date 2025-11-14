"""
Summarization Service - Summarizes transcriptions using the service framework.
"""
import datetime
from pathlib import Path
from src.pipeline.AgentSummarizer import OpenAISummarizerAgent
from src.utils.file_manager import FileManager
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.utils.postgresql_client import VideoStatus
from src.utils.mongodb_client import mongodb_client
import aiofiles


class SummarizationService(ServiceTemplate[str]):
    def __init__(self):
        super().__init__("summarization")
        self.summarizer_agent = OpenAISummarizerAgent(is_openai_runtime=True, logger=self.logger)

    async def execute_pipeline(self, video, video_id: str) -> str:
        # Check if working file path is available (contains the transcription file path for summarization)
        if not video.working_file_path:
            self.logger.error("[%s] Working file path not available in database", video_id)
            return None

        transcription_path = Path(video.working_file_path)
        if not transcription_path.exists():
            self.logger.error("[%s] File at working path not found: %s", video_id, transcription_path)
            return None

        # Read transcription content
        async with aiofiles.open(transcription_path, "r", encoding="utf-8") as f:
            transcription_text = await f.read()

        # Generate summary using the pipeline tool (automatically logs status)
        summary_text = await self.summarizer_agent.summary_call(transcription_text, video_id)

        # Update MongoDB summary
        if summary_text:
            result = mongodb_client.summaries.update_one(
                {"video_id": video_id},
                {"$set": {"video_id": video_id, "summary": summary_text, "job_id": video.job_id}},
                upsert=True
            )
            self.logger.info("[%s] SUCCESS: Summary saved to MongoDB with upsert result: %s.", video_id, result.upserted_id is not None or result.modified_count > 0)

        return summary_text

    async def get_working_file_path(self, video_id: str, video, result: str) -> str:
        """
        For summarization, we don't set a working file path as it's the final step in the pipeline.
        """
        return None  # Summarization is the final step, no further file processing needed

    def build_event_payload(self, video_id: str, video, result: str) -> dict:
        return {
            "video_id": video_id,
            "job_id": video.job_id,
            "summarized_at": datetime.datetime.utcnow().isoformat(),
            "summary_length": len(result)
        }


if __name__ == "__main__":
    # Create and run the service
    service = SummarizationService()
    service.run()