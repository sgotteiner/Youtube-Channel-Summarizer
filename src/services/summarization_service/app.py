"""
Summarization Service - Summarizes transcriptions using the service framework.
"""
from src.pipeline.AgentSummarizer import OpenAISummarizerAgent
from src.patterns.ServiceTemplatePattern import ServiceTemplate
from src.utils.mongodb_client import mongodb_client
import aiofiles


class SummarizationService(ServiceTemplate[str]):
    def __init__(self):
        from src.enums.service_enums import ServiceType
        super().__init__(ServiceType.SUMMARIZATION)
        self.summarizer_agent = OpenAISummarizerAgent(is_openai_runtime=True, logger=self.logger)

    def get_input_file_path(self, video_paths):
        """
        Summarization service needs the transcription file as input.
        """
        return video_paths["transcription"]  # Input is the transcription file

    async def perform_specific_operation(self, video, input_file_path, video_paths, video_id: str) -> str:
        # Summarization service needs the input transcription file path
        transcription_path = input_file_path

        # Read transcription content
        async with aiofiles.open(transcription_path, "r", encoding="utf-8") as f:
            transcription_text = await f.read()

        # Generate summary using the pipeline tool (automatically logs status)
        summary_text = None
        try:
            summary_text = await self.summarizer_agent.summary_call(transcription_text, video_id)
            if not summary_text:
                self.logger.info(f"[{video_id}] OpenAI returned empty summary. Saving transcription as summary instead.")
                # If OpenAI summarization returns empty or None, save the original transcription as the summary
                summary_text = transcription_text
        except Exception as e:
            self.logger.warning(f"[{video_id}] OpenAI summarization failed: {e}. Saving transcription as summary to preserve content.")
            # If OpenAI summarization fails completely, save the original transcription as the summary
            summary_text = transcription_text

        # Update MongoDB summary
        if summary_text:
            result = mongodb_client.summaries.update_one(
                {"video_id": video_id},
                {"$set": {"video_id": video_id, "summary": summary_text, "job_id": getattr(video, 'job_id', 'unknown')}},  # Using getattr to handle cases where video doesn't have job_id
                upsert=True
            )
            self.logger.info("[%s] SUCCESS: Summary saved to MongoDB with upsert result: %s.", video_id, result.upserted_id is not None or result.modified_count > 0)
        else:
            # Even if the summary is None, we want to log that we're preserving content
            self.logger.warning(f"[{video_id}] No summary content available after processing. Original transcription was likely available but summarization failed.")

        return summary_text

    def get_service_specific_event_fields(self, video_id: str, video, result: str) -> dict:
        return {
            "summary_length": len(result) if result else 0
        }


if __name__ == "__main__":
    # Create and run the service
    service = SummarizationService()
    service.run()