"""
Encapsulates the entire processing pipeline for a single YouTube video.
"""
import os
from pathlib import Path
import logging
from typing import Dict
from ChannelVideoDownloader import VideoDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from yt_dlp import YoutubeDL
from FileManager import FileManager

class VideoProcessor:
    """
    Orchestrates the processing of a single video.
    """
    def __init__(self, video_data: dict, paths: dict, services: dict, is_save_only_summaries: bool, logger: logging.Logger):
        self.video_data = video_data
        self.paths = paths
        self.services = services
        self.is_save_only_summaries = is_save_only_summaries
        self.logger = logger

        self.video_url = self.video_data["video_url"]
        self.video_id = self.video_data["video_id"]
        self.video_title = self.video_data["video_title"]
        self.upload_date = self.video_data["upload_date"]
        self.has_captions = self.video_data["has_captions"]

        # Use the centralized FileManager for consistent naming
        self.base_filename = FileManager.get_base_filename(self.video_data)
        self._prepare_paths()

    def _prepare_paths(self):
        """Constructs the full paths for all files related to this video."""
        self.video_path = self.paths['videos'] / f"{self.base_filename}.mp4"
        self.audio_path = self.paths['audios'] / f"{self.base_filename}.wav"
        self.transcription_path = self.paths['transcriptions'] / f"{self.base_filename}.txt"
        self.summary_path = self.paths['summaries'] / f"{self.base_filename}.txt"

    def process(self):
        """Main entry point to start the processing of the video."""
        self.logger.info(f"--- Starting processing for video: '{self.video_title}' ---")
        
        transcription_text = self._get_transcription()
        if transcription_text:
            self._summarize_and_cleanup(transcription_text)
        else:
            self.logger.warning(f"Could not obtain transcription for '{self.video_title}'. Skipping summarization.")
        self.logger.info(f"--- Finished processing for video: '{self.video_title}' ---")

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
            transcription = self._download_captions()
            if transcription:
                self.logger.info("Successfully downloaded and processed captions.")
                return transcription
            self.logger.warning("Failed to download captions. Falling back to audio transcription.")
        else:
            self.logger.info("Video has no captions. Proceeding with audio transcription.")

        return self._transcribe_audio_from_video()

    def _download_captions(self) -> str | None:
        """Downloads and processes captions for the video using yt-dlp."""
        ydl_opts = {
            "skip_download": True, "subtitleslangs": ["en"], "subtitlesformat": "vtt",
            "quiet": True, "outtmpl": str(self.transcription_path.parent / self.video_id) + ".%(ext)s",
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
                lang = "en"
                if info.get("subtitles", {}).get(lang):
                    ydl_opts["writesubtitles"] = True
                elif info.get("automatic_captions", {}).get(lang):
                    ydl_opts["writeautomaticsub"] = True
                else:
                    return None
                
                ydl.download([self.video_url])
                raw_subtitle_path = self.transcription_path.parent / f"{self.video_id}.{lang}.vtt"
                
                if raw_subtitle_path.exists():
                    text = self._process_vtt_file(raw_subtitle_path)
                    self.transcription_path.write_text(text, encoding="utf-8")
                    os.remove(raw_subtitle_path)
                    return text
        except Exception as e:
            self.logger.error(f"Error during subtitle download for '{self.video_title}': {e}")
        return None

    def _process_vtt_file(self, vtt_path: Path) -> str:
        """Cleans a VTT subtitle file, returning only the spoken text."""
        lines = vtt_path.read_text(encoding="utf-8").splitlines()
        cleaned_lines = [
            line.strip() for line in lines 
            if "-->" not in line and not line.startswith(("WEBVTT", "Kind:", "Language:")) and line.strip()
        ]
        return " ".join(cleaned_lines)

    def _transcribe_audio_from_video(self) -> str | None:
        """Manages the full audio transcription pipeline: download -> extract -> transcribe."""
        self.logger.info("Fallback pipeline: Transcribing from audio.")
        video_downloader: VideoDownloader = self.services['video_downloader']
        audio_extractor: AudioExtractor = self.services['audio_extractor']
        audio_transcriber: AudioTranscriber = self.services['audio_transcriber']

        if not self.video_path.exists():
            self.logger.info(f"Downloading video to: {self.video_path}")
            video_downloader.download_video(self.video_url, self.video_title, self.upload_date, self.video_id, self.paths['videos'])
        if not self.video_path.exists():
            self.logger.error("Video download failed. Cannot transcribe.")
            return None

        if not self.audio_path.exists():
            self.logger.info(f"Extracting audio to: {self.audio_path}")
            audio_extractor.extract_audio(self.video_path, self.audio_path)
        if not self.audio_path.exists():
            self.logger.error("Audio extraction failed. Cannot transcribe.")
            return None
            
        self.logger.info(f"Transcribing audio file: {self.audio_path}")
        transcription = audio_transcriber.transcribe_audio(self.audio_path)
        if transcription:
            self.logger.info("Transcription successful. Saving to file.")
            self.transcription_path.write_text(transcription, encoding="utf-8")
        return transcription

    def _summarize_and_cleanup(self, transcription_text: str):
        """Generates a summary and optionally cleans up intermediate files."""
        self.logger.info("Step 2: Summarizing transcription...")
        summarizer: OpenAISummarizerAgent = self.services['summarizer']
        
        summary = summarizer.summary_call(transcription_text)
        if summary:
            self.summary_path.write_text(summary, encoding="utf-8")
            self.logger.info(f"Summarization complete. Summary saved to: {self.summary_path}")
            if self.is_save_only_summaries:
                self.logger.info("Step 3: Cleaning up intermediate files...")
                self._cleanup_intermediate_files()
        else:
            self.logger.error(f"Summarization failed for '{self.video_title}'.")

    def _cleanup_intermediate_files(self):
        """Deletes the video, audio, and transcription files for the video."""
        for file_path in [self.video_path, self.audio_path, self.transcription_path]:
            if file_path.exists():
                try:
                    os.remove(file_path)
                    self.logger.info(f"Deleted: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error deleting {file_path}: {e}")