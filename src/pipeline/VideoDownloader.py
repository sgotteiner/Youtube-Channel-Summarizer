"""
Module for downloading YouTube audio and captions.
"""
import os
from pathlib import Path
from typing import Optional
import logging
from yt_dlp import YoutubeDL
import aiofiles
from src.utils.common_logger import log_success_by_video_id, log_error_by_video_id, log_warning_by_video_id, sanitize_filename


class AudioDownloader:
    """Handles the downloading of audio from YouTube videos."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _check_file_exists_and_log(self, filepath: Path, title: str, video_id: str, file_type: str) -> Optional[Path]:
        """Check if the file already exists and log appropriately."""
        if filepath.exists():
            self.logger.info(f"{file_type} '{title}' already exists. Skipping download.")
            # Log the completion status with video_id format too
            log_success_by_video_id(self.logger, video_id, f"{file_type} downloaded successfully to: %s", filepath)
            return filepath
        return None

    def download_audio(self, youtube_video_url: str, video_title: str, upload_date: str, video_id: str, path_to_save_audio: Path) -> Optional[Path]:
        """
        Downloads audio from a YouTube URL and converts to WAV format using yt-dlp.

        Args:
            youtube_video_url (str): The YouTube URL to download from
            video_title (str): Title of the video (for filename)
            upload_date (str): Upload date of the video
            video_id (str): The video ID for logging purposes
            path_to_save_audio (Path): Path where the audio will be saved

        Returns:
            Optional[Path]: Path to the downloaded audio in WAV format, or None if failed
        """
        sanitized_filename = f"{sanitize_filename(video_title)}-{upload_date}-{video_id}"
        # Note: yt-dlp will add the .wav extension automatically
        audio_filepath = path_to_save_audio / f"{sanitized_filename}.wav"

        # Check if file already exists
        existing_file = self._check_file_exists_and_log(audio_filepath, video_title, video_id, "Audio")
        if existing_file:
            return existing_file

        ydl_opts = {
            'format': 'bestaudio/best',  # Download the best available audio
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',      # Convert to WAV format
                'preferredquality': '0',      # Highest quality
            }],
            'postprocessor_args': [
                '-ar', '16000',  # Optional: set audio sampling rate
            ],
            'prefer_ffmpeg': True,
            'extractaudio': True,
            'keepvideo': False,
            'outtmpl': str(path_to_save_audio / f'{sanitized_filename}.%(ext)s'),  # Output path with filename
        }

        try:
            self.logger.info(f"Downloading audio to {audio_filepath}...")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_video_url])

            self.logger.info("Audio download and conversion successful.")

            # Log the completion status with video_id format
            log_success_by_video_id(self.logger, video_id, "Audio downloaded successfully to: %s", audio_filepath)
            return audio_filepath
        except Exception as e:
            self.logger.error(f'Error downloading or converting audio: {e}')
            log_error_by_video_id(self.logger, video_id, "Failed to download or convert audio")
            return None


class CaptionsDownloader:
    """Handles downloading and processing YouTube captions to clean text transcription."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def download_captions(self, video_id: str, destination_path: Path) -> Optional[Path]:
        """
        Downloads the English captions for a video to the specified path.
        Returns the path to the downloaded .vtt file if successful, otherwise None.
        Prioritizes user-uploaded subtitles, falls back to auto-generated captions.
        """
        self.logger.info(f"Attempting to download captions for video ID: {video_id}")

        url = f"https://www.youtube.com/watch?v={video_id}"

        # First, let's get info to check what's available
        info_ydl_opts = {
            'skip_download': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'subtitleslangs': ['en'],
            'quiet': True,
        }

        try:
            with YoutubeDL(info_ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            manual_subs = info.get("subtitles", {}).get("en")
            auto_subs = info.get("automatic_captions", {}).get("en")

            # Define the path template
            outtmpl = str(destination_path / f"{video_id}.%(ext)s")

            if manual_subs:  # User-uploaded subtitles available
                self.logger.info(f"[{video_id}] User-uploaded captions available. Downloading...")
                download_ydl_opts = {
                    'skip_download': True,
                    'writesubtitles': True,
                    'subtitleslangs': ['en'],
                    'subtitlesformat': 'vtt',
                    'outtmpl': outtmpl,
                    'quiet': True,
                }
                with YoutubeDL(download_ydl_opts) as ydl:
                    ydl.download([url])

                # Look for the downloaded file
                for file in destination_path.glob(f"{video_id}.en.vtt"):
                    self.logger.info(f"Successfully downloaded user-uploaded captions to {file}")
                    return file
            elif auto_subs:  # Auto-generated captions available
                self.logger.info(f"[{video_id}] Auto-generated captions available. Downloading...")
                download_ydl_opts = {
                    'skip_download': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['en'],
                    'subtitlesformat': 'vtt',
                    'outtmpl': outtmpl,
                    'quiet': True,
                }
                with YoutubeDL(download_ydl_opts) as ydl:
                    ydl.download([url])

                # Look for the downloaded auto-caption file
                for file in destination_path.glob(f"{video_id}.en.vtt"):
                    self.logger.info(f"Successfully downloaded auto-generated captions to {file}")
                    return file
            else:
                self.logger.warning(f"[{video_id}] No captions (manual or auto-generated) available.")
                log_warning_by_video_id(self.logger, video_id, "No captions available for download.")
                return None

            # If we reach here, the download was attempted but file wasn't found
            log_warning_by_video_id(self.logger, video_id, "Caption download was attempted but no VTT file was found.")
            return None

        except Exception as e:
            self.logger.error(f"An error occurred while downloading captions for {video_id}: {e}")
            return None

    async def process_captions_to_transcription(self, vtt_path: Path, transcription_path: Path) -> bool:
        """
        Processes a VTT caption file and converts it to a clean text transcription.

        Args:
            vtt_path: Path to the downloaded VTT caption file
            transcription_path: Path where the clean transcription should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiofiles.open(vtt_path, "r", encoding="utf-8") as f:
                lines = (await f.read()).splitlines()

            # Clean the VTT content (same logic as in VideoProcessor)
            cleaned_lines = [
                line.strip() for line in lines
                if "-->" not in line and not line.startswith(("WEBVTT", "Kind:", "Language:")) and line.strip()
            ]
            transcription_text = " ".join(cleaned_lines)

            # Save the cleaned transcription
            async with aiofiles.open(transcription_path, "w", encoding="utf-8") as f:
                await f.write(transcription_text)

            # Remove the raw VTT file after processing
            os.remove(vtt_path)

            self.logger.info(f"Caption file processed successfully. Saved transcription to {transcription_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error processing caption file {vtt_path}: {e}")
            return False


class VideoDataDownloader:
    """Simple coordinator that downloads either audio or captions based on availability."""
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.audio_downloader = AudioDownloader(logger)
        self.captions_downloader = CaptionsDownloader(logger)

    async def download(self, has_captions: bool, video_id: str, video_title: str, upload_date: str, video_paths: dict) -> Optional[Path]:
        """
        Downloads either captions or audio based on the has_captions flag.
        """
        if has_captions:
            # Download and process captions to transcription
            vtt_path = self.captions_downloader.download_captions(video_id, video_paths["transcription"].parent)
            if vtt_path:
                success = await self.captions_downloader.process_captions_to_transcription(vtt_path, video_paths["transcription"])
                if success:
                    return video_paths["transcription"]

        # If captions not available or processing failed, download audio
        return self.audio_downloader.download_audio(
            f"https://www.youtube.com/watch?v={video_id}",
            video_title,
            upload_date,
            video_id,
            video_paths["audio"].parent
        )