import os
from pathlib import Path
import concurrent.futures
from functools import partial
import logging
import re # Import re for sanitizing filenames

from yt_dlp import YoutubeDL
from ChannelVideoDownloader import ChannelVideosDownloader, VideoDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from logger import Logger

# Configure logging
log_file_path = 'processing.log'
logger = Logger(__name__, log_file_path).get_logger()


def process_video(video_data_item: dict, path_to_save_videos: Path, path_to_save_audios: Path, path_to_save_transcriptions: Path, path_to_save_summaries: Path, video_downloader_instance: VideoDownloader, audio_extractor_instance: AudioExtractor, audio_transcriber_instance: AudioTranscriber, summarizer: OpenAISummarizerAgent, is_save_only_summaries: bool, logger: logging.Logger):
    video_url = video_data_item["video_url"]
    video_id = video_data_item["video_id"]
    video_title = video_data_item["video_title"]
    upload_date = video_data_item["upload_date"]
    has_captions = video_data_item["has_captions"]

    logger.info(f"Starting processing for video: {video_title} ({video_url})")

    # Sanitize video title for use in filenames
    sanitized_video_title = re.sub(r'[\\/:*?"<>|]', '', video_title) # Remove invalid characters
    sanitized_video_title = sanitized_video_title[:100] # Truncate to avoid excessively long filenames

    # Define paths for this specific video
    base_filename = f"{sanitized_video_title}-{upload_date}"
    video_path = path_to_save_videos / f"{base_filename}.mp4"
    audio_path = path_to_save_audios / f"{base_filename}.wav"
    transcription_path = path_to_save_transcriptions / f"{base_filename}.txt"
    summary_path = path_to_save_summaries / f"{base_filename}.txt"



    # --- 0. Check for existing summary ---
    if summary_path.exists():
        logger.info(f"Summary for {video_title} already exists. Skipping all processing for this video.")
        return

    transcription_text = None

    # --- 1. Check for existing transcription ---
    if transcription_path.exists():
        logger.info(f"Transcription for {video_title} already exists. Reading from file.")
        with open(transcription_path, "r", encoding="utf-8") as f:
            transcription_text = f.read()
    else:
        # --- 2. Attempt to use Captions (User-uploaded then Auto-generated) ---
        caption_downloaded = False
        if has_captions: # Only attempt if metadata indicates captions might exist
            logger.info(f"Attempting to download captions for {video_title} ({video_url}).")
            def _download_and_process_subtitle(url, lang, out_path_base):
                ydl_opts = {
                    "skip_download": True,
                    "subtitleslangs": [lang],
                    "subtitlesformat": "vtt",  # Prefer vtt
                    "quiet": True,
                    "outtmpl": str(out_path_base.parent / video_id) + ".%(ext)s", # Use video_id for initial download
                }
                downloaded_raw_subtitle_path = None
                try:
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        
                        # Prioritize user-uploaded subtitles
                        if info.get("subtitles", {}).get(lang):
                            logger.info(f"User-uploaded {lang} captions found for {video_title}. Downloading...")
                            ydl_opts["writesubtitles"] = True
                            ydl.download([url])
                            downloaded_raw_subtitle_path = out_path_base.parent / f"{video_id}.{lang}.vtt"
                        elif info.get("automatic_captions", {}).get(lang):
                            logger.info(f"Auto-generated {lang} captions found for {video_title}. Downloading...")
                            ydl_opts["writeautomaticsub"] = True
                            ydl.download([url])
                            downloaded_raw_subtitle_path = out_path_base.parent / f"{video_id}.{lang}.vtt"
                        else:
                            logger.info(f"No {lang} captions (user-uploaded or auto-generated) found for {video_title}.")
                            return None
                    if downloaded_raw_subtitle_path and downloaded_raw_subtitle_path.exists():
                        with open(downloaded_raw_subtitle_path, "r", encoding="utf-8") as f:
                            raw_caption_content = f.read()
                        
                        # Basic cleanup for WebVTT format
                        if downloaded_raw_subtitle_path.suffix == ".vtt":
                            lines = raw_caption_content.splitlines()
                            cleaned_lines = []
                            for line in lines:
                                if "-->" not in line and not line.startswith("WEBVTT") and not line.startswith("Kind:") and not line.startswith("Language:") and line.strip() != "":
                                    cleaned_lines.append(line.strip())
                            cleaned_transcription_text = " ".join(cleaned_lines)
                        else:
                            cleaned_transcription_text = raw_caption_content # For other formats, use as is or add more robust parsing
                        # Save the cleaned transcription to the final transcription_path
                        with open(out_path_base.with_suffix(".txt"), "w", encoding="utf-8") as f:
                            f.write(cleaned_transcription_text)
                        logger.info(f"Successfully processed and saved captions for {video_title} to {out_path_base.with_suffix(".txt")}.")
                        os.remove(downloaded_raw_subtitle_path) # Clean up the raw caption file
                        return out_path_base.with_suffix(".txt")
                    else:
                        logger.warning(f"Downloaded caption file not found for {video_title} at {downloaded_raw_subtitle_path}. This might indicate an issue with yt_dlp or file naming.")
                        return None
                except Exception as e:
                    logger.error(f"Error during subtitle download or processing for {video_title}: {e}")
                    return None
            # Attempt to download and process captions
            transcription_file_from_captions = _download_and_process_subtitle(video_url, "en", transcription_path.with_suffix(""))
            if transcription_file_from_captions:
                with open(transcription_file_from_captions, "r", encoding="utf-8") as f:
                    transcription_text = f.read()
            else:
                logger.warning(f"No captions successfully processed for {video_title}. Proceeding with audio transcription fallback.")

    # --- 4. Summarize Transcription ---
    if transcription_text:
        # Define the potential experimental summary path
        experimental_summary_path = path_to_save_summaries.parent / 'experimental' / summary_path.name

        # If OpenAI runtime is ON and an experimental summary exists, delete it
        if summarizer.is_openai_runtime and experimental_summary_path.exists():
            logger.info(f"OpenAI runtime is ON. Deleting existing experimental summary for {video_title}: {experimental_summary_path}")
            try:
                os.remove(experimental_summary_path)
                logger.info(f"Successfully deleted experimental summary: {experimental_summary_path}")
                # Check if the experimental folder is empty and delete it
                if not any(experimental_summary_path.parent.iterdir()):
                    os.rmdir(experimental_summary_path.parent)
                    logger.info(f"Deleted empty experimental summary folder: {experimental_summary_path.parent}")
            except Exception as e:
                logger.error(f"Error deleting experimental summary {experimental_summary_path}: {e}")

        if not summary_path.exists(): # Re-check in case of parallel processing race condition
            logger.info(f"Starting summarization for {video_title}...")
            summary = summarizer.summary_call(transcription_text)
            if summary:
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary)
                logger.info(f"Summarization complete for {video_title}.")

                # --- 5. Conditional Deletion of Intermediate Files ---
                if is_save_only_summaries:
                    logger.info(f"is_save_only_summaries is True. Deleting intermediate files for {video_title}.")
                    for file_to_delete in [video_path, audio_path, transcription_path]:
                        if file_to_delete.exists():
                            try:
                                os.remove(file_to_delete)
                                logger.info(f"Deleted: {file_to_delete}")
                            except Exception as e:
                                logger.error(f"Error deleting {file_to_delete}: {e}")
            else:
                logger.error(f"Summarization failed for {video_title}.")
        else:
            logger.info(f"Summary for {video_title} already exists. Skipping summarization.")
    else:
        logger.warning(f"No transcription available for {video_title}. Skipping summarization.")
    
    logger.info(f"Finished processing for video: {video_title}")


def main():
    # --- Configuration ---
    channel_name = 'Tech With Tim'
    num_videos_to_process = 2
    max_video_length = 10  # in minutes, set to None for no limit
    is_openai_runtime = True  # Set to True to make real API calls, False for mocked responses
    is_save_only_summaries = True # Set to True to delete intermediate files after summary is saved

    # --- Setup Directories ---
    path_to_save_videos = Path(f'./channel_videos/{channel_name}')
    path_to_save_audios = Path(f'./channel_audios/{channel_name}')
    path_to_save_summaries = Path(f'./channel_summaries/{channel_name}')

    for p in [path_to_save_videos, path_to_save_audios, path_to_save_summaries]:
        p.mkdir(parents=True, exist_ok=True)

    # --- Initialize Core Components ---
    video_downloader_instance = VideoDownloader(logger)
    audio_extractor_instance = AudioExtractor(logger)
    audio_transcriber_instance = AudioTranscriber(logger)

    # Define base transcription path (always standard)
    path_to_save_transcriptions = Path(f'./channel_transcriptions/{channel_name}')
    path_to_save_transcriptions.mkdir(parents=True, exist_ok=True)

    # Initialize Summarizer Agent
    summarizer = OpenAISummarizerAgent(is_openai_runtime, logger)

    # Dynamically set the final summary path based on runtime flag
    final_path_to_save_summaries = path_to_save_summaries
    if not is_openai_runtime:
        final_path_to_save_summaries = path_to_save_summaries / 'experimental'
        final_path_to_save_summaries.mkdir(parents=True, exist_ok=True)

    # --- 1. Get Video Metadata ---
    logger.info(f"--- Retrieving metadata for latest {num_videos_to_process} videos for channel: {channel_name} ---")
    channel_video_metadata_fetcher = ChannelVideosDownloader(channel_name, num_videos_to_process, max_video_length, logger)
    videos_metadata = channel_video_metadata_fetcher.video_data
    logger.info("--- Metadata retrieval complete ---")

    # --- 2. Process each video ---
    logger.info("\n--- Starting to process videos ---")

    # Using ThreadPoolExecutor for parallel processing of videos
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for video_data_item in videos_metadata:
            futures.append(executor.submit(process_video, 
                                            video_data_item=video_data_item,
                                            path_to_save_videos=path_to_save_videos,
                                            path_to_save_audios=path_to_save_audios,
                                            path_to_save_transcriptions=path_to_save_transcriptions,
                                            path_to_save_summaries=final_path_to_save_summaries,
                                            video_downloader_instance=video_downloader_instance,
                                            audio_extractor_instance=audio_extractor_instance,
                                            audio_transcriber_instance=audio_transcriber_instance,
                                            summarizer=summarizer,
                                            is_save_only_summaries=is_save_only_summaries,
                                            logger=logger))
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result() # This will re-raise any exceptions caught during the execution of process_video
            except Exception as exc:
                logger.error(f'Video processing generated an exception: {exc}')

    logger.info("\n--- All videos processed. ---")


if __name__ == '__main__':
    main()