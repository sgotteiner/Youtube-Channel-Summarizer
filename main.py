"""
Main orchestrator for the YouTube Channel Summarizer pipeline.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from VideoDownloader import VideoDownloader
from AudioTranscriber import AudioTranscriber
from AudioExtractor import AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from logger import Logger
from VideoProcessor import VideoProcessor
from FileManager import FileManager
from config import Config
from VideoMetadataFetcher import VideoMetadataFetcher
from VideoDiscoverer import VideoDiscoverer
import aiofiles

def initialize_services(logger: logging.Logger, file_manager: FileManager, is_openai_runtime: bool) -> dict:
    """Initializes and returns all necessary service clients."""
    return {
        'file_manager': file_manager,
        'video_downloader': VideoDownloader(logger),
        'audio_extractor': AudioExtractor(logger),
        'audio_transcriber': AudioTranscriber(logger),
        'summarizer': OpenAISummarizerAgent(is_openai_runtime, logger),
    }

async def process_video_wrapper(video_data: dict, services: dict, config: Config, logger: logging.Logger, executor: ThreadPoolExecutor):
    """
    Asynchronous wrapper function to process a single video, summarize it, and clean up.
    """
    video_processor = VideoProcessor(video_data, services, logger, executor)
    transcription_text = await video_processor.process()

    if not transcription_text:
        return

    video_id = video_data['video_id']
    logger.info(f"[{video_id}] Step 3.5: Summarizing transcription...")
    summarizer: OpenAISummarizerAgent = services['summarizer']
    summary_text = await summarizer.summary_call(transcription_text)

    if not summary_text:
        logger.error(f"[{video_id}] Summarization failed.")
        return

    file_manager: FileManager = services['file_manager']
    video_paths = file_manager.get_video_paths(video_data)
    summary_path = video_paths["summary"]
    
    async with aiofiles.open(summary_path, "w", encoding="utf-8") as f:
        await f.write(summary_text)
    logger.info(f"[{video_id}] Summarization complete. Summary saved to: {summary_path}")

    if config.is_save_only_summaries:
        logger.info(f"[{video_id}] Step 4.1: Cleaning up intermediate files...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            executor, file_manager.cleanup_intermediate_files, video_paths
        )

async def main():
    """Main async function to execute the YouTube Channel Summarizer pipeline."""
    config = Config()
    logger = Logger(__name__, config.log_file_path).get_logger()
    file_manager = FileManager(config.channel_name, config.is_openai_runtime, logger)
    services = initialize_services(logger, file_manager, config.is_openai_runtime)
    
    # Use a single executor for all blocking tasks
    executor = ThreadPoolExecutor(max_workers=5)
    
    metadata_fetcher = VideoMetadataFetcher(config.channel_name, logger)
    video_discoverer = VideoDiscoverer(logger, metadata_fetcher, file_manager, executor)

    videos_to_process = await video_discoverer.discover_videos(
        config.num_videos_to_process, 
        config.max_video_length, 
        config.apply_max_length_for_captionless_only
    )
            
    if not videos_to_process:
        logger.info("No new videos to process. Exiting.")
        return

    logger.info(f"--- Discovery complete. Found {len(videos_to_process)} videos to process. ---")
    logger.info("\n--- Starting video processing phase ---")
    
    tasks = [
        process_video_wrapper(video_data, services, config, logger, executor)
        for video_data in videos_to_process
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f'A video processing task generated an exception: {result}')

    logger.info("\n--- All processing complete. ---")

if __name__ == '__main__':
    asyncio.run(main())
