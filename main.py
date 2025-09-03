import os
from pathlib import Path
import concurrent.futures
from functools import partial
import logging

from ChannelVideoDownloader import ChannelVideosDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from logger import Logger

# Configure logging
log_file_path = 'processing.log'
logger = Logger(__name__, log_file_path).get_logger()


def process_video(video_path: Path, path_to_save_audios: Path, path_to_save_transcriptions: Path, path_to_save_summaries: Path, summarizer: OpenAISummarizerAgent, logger: logging.Logger):
    video_name = video_path.stem
    logger.info(f"Starting processing for video: {video_name}")

    # Define paths for this specific video
    audio_path = path_to_save_audios / f"{video_name}.wav"
    transcription_path = path_to_save_transcriptions / f"{video_name}.txt"
    summary_path = path_to_save_summaries / f"{video_name}.txt"

    # --- 2a. Extract Audio ---
    if not audio_path.exists():
        logger.info(f"Starting audio extraction for {video_name}...")
        AudioExtractor(str(video_path), str(audio_path), logger)
        logger.info(f"Audio extraction finished for {video_name}")
    else:
        logger.info(f"Audio for {video_name} already exists. Skipping extraction.")

    # --- 2b. Transcribe Audio ---
    if not transcription_path.exists():
        logger.info(f"Starting transcription for {video_name}...")
        if audio_path.exists():
            transcription_text = AudioTranscriber(str(audio_path), logger).transcription
            with open(transcription_path, "w", encoding="utf-8") as f:
                f.write(transcription_text)
            logger.info(f"Transcription complete for {video_name}.")
        else:
            logger.warning(f"Audio file not found for {video_name}. Skipping transcription.")
    else:
        logger.info(f"Transcription for {video_name} already exists. Skipping transcription.")

    # --- 2c. Summarize Transcription ---
    if not summary_path.exists():
        logger.info(f"Starting summarization for {video_name}...")
        try:
            with open(transcription_path, "r", encoding="utf-8") as f:
                transcription = f.read()
            
            if transcription:
                summary = summarizer.summary_call(transcription)
                if summary:
                    with open(summary_path, "w", encoding="utf-8") as f:
                        f.write(summary)
                    logger.info(f"Summarization complete for {video_name}.")
                else:
                    logger.error(f"Summarization failed for {video_name}.")
            else:
                logger.warning(f"Transcription for {video_name} is empty. Skipping summarization.")

        except FileNotFoundError:
            logger.error(f"Transcription file not found for {video_name}. Skipping summarization.")
    else:
        logger.info(f"Summary for {video_name} already exists. Skipping summarization.")
    
    logger.info(f"Finished processing for video: {video_name}")


def main():
    # --- Configuration ---
    channel_name = 'TradeIQ'
    num_videos_to_process = 7
    is_runtime = True  # Set to True to make real API calls, False for mocked responses

    # --- Setup Directories ---
    path_to_save_videos = Path(f'./channel_videos/{channel_name}')
    path_to_save_audios = Path(f'./channel_audios/{channel_name}')
    path_to_save_transcriptions = Path(f'./channel_transcriptions/{channel_name}')
    path_to_save_summaries = Path(f'./channel_summaries/{channel_name}')

    for p in [path_to_save_videos, path_to_save_audios, path_to_save_transcriptions, path_to_save_summaries]:
        p.mkdir(parents=True, exist_ok=True)

    # --- 1. Download Videos ---
    logger.info(f"--- Downloading latest {num_videos_to_process} videos for channel: {channel_name} ---")
    ChannelVideosDownloader(channel_name, str(path_to_save_videos), num_videos_to_process, logger)
    logger.info("--- Download complete ---")

    # --- Initialize Summarizer Agent ---
    summarizer = OpenAISummarizerAgent(is_runtime, logger)

    # --- 2. Process each downloaded video ---
    logger.info("\n--- Starting to process downloaded videos ---")
    downloaded_videos = [f for f in path_to_save_videos.iterdir() if f.is_file() and f.suffix == '.mp4']

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        process_func = partial(process_video, 
                               path_to_save_audios=path_to_save_audios, 
                               path_to_save_transcriptions=path_to_save_transcriptions, 
                               path_to_save_summaries=path_to_save_summaries, 
                               summarizer=summarizer,
                               logger=logger)
        
        # Using list() to ensure the map is fully consumed, thus waiting for all threads to complete.
        list(executor.map(process_func, downloaded_videos))

    logger.info("\n--- All videos processed. ---")


if __name__ == '__main__':
    main()
