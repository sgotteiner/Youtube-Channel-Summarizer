"""
Encapsulates the entire processing pipeline for a single YouTube video.
"""
import os
from pathlib import Path
import logging
from typing import Dict
from VideoDownloader import VideoDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from FileManager import FileManager

class VideoProcessor:
    """
    Orchestrates the processing of a single video.
    """
    def __init__(self, video_data: dict, services: dict, logger: logging.Logger):
        self.video_data = video_data
        self.services = services
        self.logger = logger

        self.video_url = self.video_data["video_url"]
        self.video_id = self.video_data["video_id"]
        self.video_title = self.video_data["video_title"]
        self.upload_date = self.video_data["upload_date"]
        self.has_captions = self.video_data["has_captions"]

        # Get all video-specific paths from the FileManager
        file_manager: FileManager = self.services['file_manager']
        self.video_paths = file_manager.get_video_paths(self.video_data)
        self.video_path = self.video_paths["video"]
        self.audio_path = self.video_paths["audio"]
        self.transcription_path = self.video_paths["transcription"]
        self.summary_path = self.video_paths["summary"]

    def process(self) -> str | None:
        """Main entry point to start the processing of the video."""
        self.logger.info(f"--- Starting processing for video: '{self.video_title}' ---")
        
        transcription_text = self._get_transcription()
        if not transcription_text:
            self.logger.warning(f"Could not obtain transcription for '{self.video_title}'.")
            return None
        
        self.logger.info(f"--- Finished processing for video: '{self.video_title}' ---")
        return transcription_text

    def _get_transcription(self) -> str | None:
        """
        Retrieves the transcription for the video.
        """
        self.logger.info("Step 1: Getting transcription...")
        if self.transcription_path.exists():
            self.logger.info(f"Transcription file found. Reading from: {self.transcription_path}")
            return self.transcription_path.read_text(encoding="utf-8")

        if self.has_captions:
            self.logger.info("Video has captions. Attempting to download them.")
            transcription = self._download_and_process_captions()
            if transcription:
                self.logger.info("Successfully downloaded and processed captions.")
                return transcription
            self.logger.warning("Failed to download captions. Falling back to audio transcription.")
        else:
            self.logger.info("Video has no captions. Proceeding with audio transcription.")

        return self._transcribe_video_manually()

    def _download_and_process_captions(self) -> str | None:
        """Downloads, processes, and cleans captions for the video."""
        video_downloader: VideoDownloader = self.services['video_downloader']
        file_manager: FileManager = self.services['file_manager']
        
        raw_caption_path = video_downloader.download_captions(self.video_id, file_manager.paths['transcriptions'])
        
        if raw_caption_path and raw_caption_path.exists():
            try:
                self.logger.info(f"Processing VTT file: {raw_caption_path}")
                text = self._process_vtt_file(raw_caption_path)
                
                self.transcription_path.write_text(text, encoding="utf-8")
                self.logger.info(f"Cleaned transcription saved to: {self.transcription_path}")
                
                return text
            finally:
                os.remove(raw_caption_path)
                self.logger.info(f"Deleted raw VTT file: {raw_caption_path}")
        
        return None

    def _process_vtt_file(self, vtt_path: Path) -> str:
        """Cleans a VTT subtitle file, returning only the spoken text."""
        lines = vtt_path.read_text(encoding="utf-8").splitlines()
        cleaned_lines = [
            line.strip() for line in lines 
            if "-->" not in line and not line.startswith(("WEBVTT", "Kind:", "Language:")) and line.strip()
        ]
        return " ".join(cleaned_lines)

    def _download_video(self) -> bool:
        """Downloads the video if it doesn't already exist."""
        if not self.video_path.exists():
            self.logger.info(f"Downloading video to: {self.video_path}")
            video_downloader: VideoDownloader = self.services['video_downloader']
            file_manager: FileManager = self.services['file_manager']
            video_downloader.download_video(self.video_url, self.video_title, self.upload_date, self.video_id, file_manager.paths['videos'])
        return self.video_path.exists()

    def _extract_audio(self) -> bool:
        """Extracts audio from the video if it doesn't already exist."""
        if not self.audio_path.exists():
            self.logger.info(f"Extracting audio to: {self.audio_path}")
            audio_extractor: AudioExtractor = self.services['audio_extractor']
            audio_extractor.extract_audio(self.video_path, self.audio_path)
        return self.audio_path.exists()

    def _transcribe_audio(self) -> str | None:
        """Transcribes the audio file."""
        self.logger.info(f"Transcribing audio file: {self.audio_path}")
        audio_transcriber: AudioTranscriber = self.services['audio_transcriber']
        transcription = audio_transcriber.transcribe_audio(self.audio_path)
        if transcription:
            self.logger.info("Transcription successful. Saving to file.")
            self.transcription_path.write_text(transcription, encoding="utf-8")
        return transcription

    def _transcribe_video_manually(self) -> str | None:
        """Manages the full audio transcription pipeline: download video -> extract audio -> transcribe."""
        self.logger.info("Fallback pipeline: Transcribing from audio.")

        if not self._download_video():
            self.logger.error("Video download failed. Cannot transcribe.")
            return None

        if not self._extract_audio():
            self.logger.error("Audio extraction failed. Cannot transcribe.")
            return None
            
        return self._transcribe_audio()