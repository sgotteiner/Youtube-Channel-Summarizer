"""
Main orchestrator for the YouTube Channel Summarizer pipeline.
"""
import concurrent.futures
import logging
from VideoDownloader import VideoDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from logger import Logger
from VideoProcessor import VideoProcessor
from FileManager import FileManager
from config import Config
from VideoMetadataFetcher import VideoMetadataFetcher
from VideoDiscoverer import VideoDiscoverer

def initialize_services(logger: logging.Logger, file_manager: FileManager, is_openai_runtime: bool) -> dict:
    """Initializes and returns all necessary service clients."""
    return {
        'file_manager': file_manager,
        'video_downloader': VideoDownloader(logger),
        'audio_extractor': AudioExtractor(logger),
        'audio_transcriber': AudioTranscriber(logger),
        'summarizer': OpenAISummarizerAgent(is_openai_runtime, logger),
    }

def main():
    """Main function to execute the YouTube Channel Summarizer pipeline."""
    # --- Configuration ---
    # The Config class handles loading settings from .config and .env files.
    config = Config()

    # --- Setup ---
    logger = Logger(__name__, config.log_file_path).get_logger()
    file_manager = FileManager(config.channel_name, config.is_openai_runtime, logger)
    services = initialize_services(logger, file_manager, config.is_openai_runtime)
    
    metadata_fetcher = VideoMetadataFetcher(config.channel_name, logger)
    video_discoverer = VideoDiscoverer(logger, metadata_fetcher, file_manager)

    # --- 1. Discover Videos to Process ---
    videos_to_process = video_discoverer.discover_videos(
        config.num_videos_to_process, 
        config.max_video_length, 
        config.apply_max_length_for_captionless_only
    )
            
    if not videos_to_process:
        logger.info("No new videos to process. Exiting.")
        return

    logger.info(f"--- Discovery complete. Found {len(videos_to_process)} videos to process. ---")

    # --- 2. Process Videos in Parallel ---
    logger.info("\n--- Starting video processing phase ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                VideoProcessor(video_data, services, config.is_save_only_summaries, logger).process
            )
            for video_data in videos_to_process
        ]

        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.error(f'A video processing task generated an exception: {exc}')

    logger.info("\n--- All processing complete. ---")

if __name__ == '__main__':
    main()
