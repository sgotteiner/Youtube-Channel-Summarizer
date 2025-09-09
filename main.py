import concurrent.futures
from pathlib import Path
import logging
from ChannelVideoDownloader import ChannelVideosDownloader, VideoDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from logger import Logger
from VideoProcessor import VideoProcessor

def setup_directories(channel_name: str) -> dict:
    """Creates and returns paths for storing video-related files."""
    base_paths = {
        'videos': Path(f'./channel_videos/{channel_name}'),
        'audios': Path(f'./channel_audios/{channel_name}'),
        'transcriptions': Path(f'./channel_transcriptions/{channel_name}'),
        'summaries': Path(f'./channel_summaries/{channel_name}'),
    }
    for path in base_paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return base_paths

def initialize_services(logger: logging.Logger, is_openai_runtime: bool) -> dict:
    """Initializes and returns all the necessary service clients."""
    return {
        'video_downloader': VideoDownloader(logger),
        'audio_extractor': AudioExtractor(logger),
        'audio_transcriber': AudioTranscriber(logger),
        'summarizer': OpenAISummarizerAgent(is_openai_runtime, logger),
    }

def main():
    # --- Configuration ---
    channel_name = 'Tech With Tim'
    num_videos_to_process = 2
    max_video_length = 10  # in minutes, set to None for no limit
    is_openai_runtime = True
    is_save_only_summaries = True

    # --- Setup ---
    log_file_path = 'processing.log'
    logger = Logger(__name__, log_file_path).get_logger()
    
    paths = setup_directories(channel_name)
    services = initialize_services(logger, is_openai_runtime)

    if not is_openai_runtime:
        experimental_path = paths['summaries'] / 'experimental'
        experimental_path.mkdir(parents=True, exist_ok=True)
        paths['summaries'] = experimental_path

    # --- 1. Get Video Metadata ---
    logger.info(f"--- Retrieving metadata for latest {num_videos_to_process} videos for channel: {channel_name} ---")
    channel_video_metadata_fetcher = ChannelVideosDownloader(channel_name, num_videos_to_process, max_video_length, logger)
    videos_metadata = channel_video_metadata_fetcher.video_data
    logger.info("--- Metadata retrieval complete ---")

    # --- 2. Process each video in parallel ---
    logger.info("\n--- Starting to process videos ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for video_data_item in videos_metadata:
            processor = VideoProcessor(video_data_item, paths, services, is_save_only_summaries, logger)
            futures.append(executor.submit(processor.process))
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.error(f'Video processing generated an exception: {exc}')

    logger.info("\n--- All videos processed. ---")

if __name__ == '__main__':
    main()
