"""
Encapsulates the entire processing pipeline for a single YouTube video.
"""
import asyncio
import os
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
import aiofiles
from src.pipeline.VideoDownloader import VideoDownloader
from src.pipeline.AudioTranscriber import AudioTranscriber
from src.pipeline.AudioExtractor import AudioExtractor
from src.utils.file_manager import FileManager

class VideoProcessor:
    """
    Orchestrates the processing of a single video asynchronously.
    """
    def __init__(self, video_data: dict, services: dict, logger: logging.Logger, executor: ThreadPoolExecutor):
        self.video_data = video_data
        self.services = services
        self.logger = logger
        self.executor = executor

        self.video_id = self.video_data["video_id"]
        self.log_prefix = f"[{self.video_id}]"

        self.video_url = self.video_data["video_url"]
        self.video_title = self.video_data["video_title"]
        self.upload_date = self.video_data["upload_date"]
        self.has_captions = self.video_data["has_captions"]

        file_manager: FileManager = self.services['file_manager']
        self.video_paths = file_manager.get_video_paths(self.video_data)
        self.video_path = self.video_paths["video"]
        self.audio_path = self.video_paths["audio"]
        self.transcription_path = self.video_paths["transcription"]
        self.summary_path = self.video_paths["summary"]

    async def process(self) -> str | None:
        """Main entry point to start the processing of the video."""
        self.logger.info(f"{self.log_prefix} --- Starting processing ---")
        
        transcription_text = await self._get_transcription()
        if not transcription_text:
            self.logger.warning(f"{self.log_prefix} Could not obtain transcription. Halting processing for this video.")
            return None
        
        self.logger.info(f"{self.log_prefix} --- Finished processing ---")
        return transcription_text

    async def _get_transcription(self) -> str | None:
        """
        Retrieves the transcription for the video, prioritizing existing files and captions.
        """
        self.logger.info(f"{self.log_prefix} Step 3.2: Checking for transcription...")
        if self.transcription_path.exists():
            self.logger.info(f"{self.log_prefix} Local transcription file found. Reading from disk.")
            async with aiofiles.open(self.transcription_path, "r", encoding="utf-8") as f:
                return await f.read()

        if self.has_captions:
            self.logger.info(f"{self.log_prefix} Video has captions. Attempting caption-based transcription.")
            transcription = await self._download_and_process_captions()
            if transcription:
                self.logger.info(f"{self.log_prefix} Caption-based transcription successful.")
                return transcription
            self.logger.warning(f"{self.log_prefix} Caption download or processing failed. Falling back to manual transcription.")
        else:
            self.logger.info(f"{self.log_prefix} Video has no captions. Proceeding with manual transcription.")

        return await self._transcribe_video_manually()

    async def _download_and_process_captions(self) -> str | None:
        """Downloads, processes, and cleans captions for the video."""
        self.logger.info(f"{self.log_prefix} Step 3.3: Downloading captions.")
        video_downloader: VideoDownloader = self.services['video_downloader']
        file_manager: FileManager = self.services['file_manager']
        
        loop = asyncio.get_running_loop()
        raw_caption_path = await loop.run_in_executor(
            self.executor, video_downloader.download_captions, self.video_id, file_manager.paths['transcriptions']
        )
        
        if raw_caption_path and raw_caption_path.exists():
            try:
                self.logger.info(f"{self.log_prefix} VTT file downloaded. Processing...")
                text = await self._process_vtt_file(raw_caption_path)
                
                async with aiofiles.open(self.transcription_path, "w", encoding="utf-8") as f:
                    await f.write(text)
                self.logger.info(f"{self.log_prefix} Cleaned transcription saved to file.")
                
                return text
            finally:
                await loop.run_in_executor(self.executor, os.remove, raw_caption_path)
                self.logger.info(f"{self.log_prefix} Deleted raw VTT file.")
        
        return None

    async def _process_vtt_file(self, vtt_path: Path) -> str:
        """Cleans a VTT subtitle file, returning only the spoken text."""
        async with aiofiles.open(vtt_path, "r", encoding="utf-8") as f:
            lines = (await f.read()).splitlines()
        cleaned_lines = [
            line.strip() for line in lines 
            if "-->" not in line and not line.startswith(("WEBVTT", "Kind:", "Language:")) and line.strip()
        ]
        return " ".join(cleaned_lines)

    async def _transcribe_video_manually(self) -> str | None:
        """Manages the full audio transcription pipeline: download -> extract -> transcribe."""
        self.logger.info(f"{self.log_prefix} Step 3.4: Starting manual transcription pipeline.")
        
        if not await self._download_video():
            self.logger.error(f"{self.log_prefix} Video download failed. Cannot transcribe.")
            return None

        if not await self._extract_audio():
            self.logger.error(f"{self.log_prefix} Audio extraction failed. Cannot transcribe.")
            return None
            
        return await self._transcribe_audio()

    async def _download_video(self) -> bool:
        """Downloads the video if it doesn't already exist."""
        if not self.video_path.exists():
            self.logger.info(f"{self.log_prefix} Step 3.4a: Video file not found. Downloading...")
            video_downloader: VideoDownloader = self.services['video_downloader']
            file_manager: FileManager = self.services['file_manager']
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.executor, video_downloader.download_video, self.video_url, self.video_title, self.upload_date, self.video_id, file_manager.paths['videos']
            )
        else:
            self.logger.info(f"{self.log_prefix} Step 3.4a: Video file already exists. Skipping download.")
        return self.video_path.exists()

    async def _extract_audio(self) -> bool:
        """Extracts audio from the video if it doesn't already exist."""
        if not self.audio_path.exists():
            self.logger.info(f"{self.log_prefix} Step 3.4b: Audio file not found. Extracting from video...")
            audio_extractor: AudioExtractor = self.services['audio_extractor']
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.executor, audio_extractor.extract_audio, self.video_path, self.audio_path
            )
        else:
            self.logger.info(f"{self.log_prefix} Step 3.4b: Audio file already exists. Skipping extraction.")
        return self.audio_path.exists()

    async def _transcribe_audio(self) -> str | None:
        """Transcribes the audio file."""
        self.logger.info(f"{self.log_prefix} Step 3.4c: Transcribing audio file.")
        audio_transcriber: AudioTranscriber = self.services['audio_transcriber']
        # The transcribe_audio method is now async, so we can call it directly
        # Pass video_id to create unique chunk filenames and avoid race conditions
        transcription = await audio_transcriber.transcribe_audio(self.audio_path, video_id=self.video_id)
        if transcription:
            self.logger.info(f"{self.log_prefix} Transcription successful. Saving to file.")
            async with aiofiles.open(self.transcription_path, "w", encoding="utf-8") as f:
                await f.write(transcription)
        return transcription