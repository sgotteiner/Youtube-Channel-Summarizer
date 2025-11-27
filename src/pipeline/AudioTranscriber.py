"""
Module for audio transcription from audio files.

This module provides the following class:
-   AudioTranscriber: Transcribes audio files to text using speech recognition.
"""
import os
import speech_recognition as sr
from pydub import AudioSegment
from pathlib import Path
import logging
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import aiofiles
from src.utils.common_logger import log_success_by_video_id, log_error_by_video_id
from src.constants.service_constants import AUDIO_FILE_EXTENSION
from src.constants.time_constants import AUDIO_CHUNK_LENGTH_MS


class AudioTranscriber:
    """
    Transcribes audio files to text by breaking them into manageable chunks.
    """
    def __init__(self, logger: logging.Logger):
        """
        Initializes the AudioTranscriber.

        Args:
            logger (logging.Logger): The logger instance for logging messages.
        """
        self.logger = logger
        self.recognizer = sr.Recognizer()
        # Use a thread pool for CPU-bound operations
        self.executor = ThreadPoolExecutor(max_workers=4)

    def _sanitize_filename_for_chunks(self, audio_file_prefix: str) -> str:
        """Sanitize the filename for use in chunk names."""
        # Remove any spaces or special characters that might be problematic for filenames
        return audio_file_prefix.replace(" ", "_").replace("-", "_")

    def _prepare_chunks_info(self, full_audio, chunk_length_ms: int, chunk_base_name: str):
        """Prepare information about audio chunks."""
        chunks_info = []
        for i, start_ms in enumerate(range(0, len(full_audio), chunk_length_ms)):
            end_ms = start_ms + chunk_length_ms
            chunk = full_audio[start_ms:end_ms]
            chunk_filename = f"{chunk_base_name}_chunk_{i}{AUDIO_FILE_EXTENSION}"
            chunks_info.append((chunk, chunk_filename, i))
        return chunks_info

    def _export_chunks_to_files(self, chunks_info):
        """Export all audio chunks to temporary files."""
        for chunk, chunk_filename, i in chunks_info:
            chunk.export(chunk_filename, format="wav")

    async def _process_chunks_concurrently(self, chunks_info):
        """Process transcription chunks concurrently."""
        # Process transcriptions concurrently
        loop = asyncio.get_event_loop()
        tasks = []
        for _, chunk_filename, chunk_index in chunks_info:
            task = loop.run_in_executor(self.executor, self._transcribe_chunk_sync, chunk_filename, chunk_index)
            tasks.append(task)

        transcribed_chunks = await asyncio.gather(*tasks, return_exceptions=True)
        return transcribed_chunks

    def _transcribe_chunk_sync(self, chunk_filename: str, chunk_index: int) -> str:
        """
        Transcribes a single audio chunk using Google Speech Recognition.

        Args:
            chunk_filename (str): The filename of the audio chunk to transcribe.
            chunk_index (int): The index of the chunk, for logging purposes.

        Returns:
            str: The transcribed text, or an error/unintelligible message.
        """
        self.logger.info(f"Chunk {chunk_index}: Starting transcription...")
        try:
            with sr.AudioFile(chunk_filename) as source:
                audio = self.recognizer.record(source)
            # Recognize the speech in the audio chunk
            text = self.recognizer.recognize_google(audio) + '\n'
            self.logger.info(f"Chunk {chunk_index}: Successfully transcribed ({len(text.strip())} chars)")
            return text
        except sr.UnknownValueError:
            self.logger.warning(f"Chunk {chunk_index}: Google Speech Recognition could not understand audio.")
            return "[unintelligible]\n"
        except sr.RequestError as e:
            self.logger.error(f"Chunk {chunk_index}: Could not request results from Google service; {e}")
            return f"[request error: {e}]\n"
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during transcription of chunk {chunk_index}: {e}")
            return "[unexpected transcription error]\n"

    def _cleanup_temp_files(self, chunks_info):
        """Clean up temporary chunk files."""
        for _, chunk_filename, _ in chunks_info:
            try:
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)
            except Exception as e:
                self.logger.warning(f"Could not remove temporary file {chunk_filename}: {e}")

    def _handle_transcription_results(self, transcribed_chunks):
        """Handle transcription results, including errors."""
        final_chunks = []
        for i, chunk_result in enumerate(transcribed_chunks):
            if isinstance(chunk_result, Exception):
                self.logger.error(f"Error processing chunk {i}: {chunk_result}")
                final_chunks.append("[transcription error]\n")
            else:
                final_chunks.append(chunk_result)
        return final_chunks

    def _check_audio_file_exists(self, audio_path: Path, video_id: str = None) -> bool:
        """Check if the audio file exists."""
        if not audio_path.exists():
            if video_id:
                log_error_by_video_id(self.logger, video_id, "Audio file not found for transcription: %s", audio_path)
            else:
                self.logger.error("Audio file not found for transcription: %s", audio_path)
            return False
        return True

    def _create_chunk_base_name(self, audio_path: Path, video_id: str = None) -> str:
        """Create a base name for audio chunks."""
        audio_file_prefix = audio_path.stem
        return f"{self._sanitize_filename_for_chunks(audio_file_prefix)}_{video_id}" if video_id else audio_file_prefix

    async def transcribe_audio(self, audio_path: Path, chunk_length_ms: int = AUDIO_CHUNK_LENGTH_MS, video_id: str = None) -> Optional[str]:
        """
        Transcribes a full audio file by splitting it into chunks.

        This approach is necessary to handle long audio files that might otherwise
        fail with speech recognition APIs.

        Args:
            audio_path (Path): The path to the audio file.
            chunk_length_ms (int): The length of each chunk in milliseconds.
            video_id (str, optional): The video ID to create unique chunk filenames and avoid race conditions.

        Returns:
            Optional[str]: The full transcribed text, or None if the file doesn't exist.
        """
        if not self._check_audio_file_exists(audio_path, video_id):
            return None

        full_audio = AudioSegment.from_file(audio_path)
        self.logger.info(f"Starting audio transcription for {audio_path}...")

        # Create unique chunk filenames to avoid race conditions when multiple videos are being processed
        chunk_base_name = self._create_chunk_base_name(audio_path, video_id)

        # Prepare chunks
        chunks_info = self._prepare_chunks_info(full_audio, chunk_length_ms, chunk_base_name)

        # Process chunks concurrently
        self.logger.info(f"Starting to process {len(chunks_info)} audio chunks concurrently...")

        # Export all chunks to temporary files first
        self._export_chunks_to_files(chunks_info)

        # Process transcriptions concurrently
        transcribed_chunks = await self._process_chunks_concurrently(chunks_info)

        # Clean up temporary files after processing
        self._cleanup_temp_files(chunks_info)

        # Handle any exceptions during transcription
        final_chunks = self._handle_transcription_results(transcribed_chunks)

        transcription_result = " ".join(final_chunks)
        self.logger.info(f"Audio transcription finished for {audio_path}. Combined {len([t for t in final_chunks if t.strip() and '[transcription error]' not in t])} successful chunks.")

        # Automatically log completion status with video_id if provided
        if video_id:
            if transcription_result:
                log_success_by_video_id(self.logger, video_id, "Transcription completed (length: %d characters)", len(transcription_result))

        return transcription_result

    async def _save_transcription_to_file(self, transcription_text: str, output_path: Path, video_id: str = None) -> Optional[Path]:
        """
        Saves the transcription text to the specified output file.

        Args:
            transcription_text (str): The transcribed text to save.
            output_path (Path): The path where the transcription should be saved.
            video_id (str, optional): The video ID for logging purposes.

        Returns:
            Optional[Path]: Path to the saved transcription file, or None if operation failed.
        """
        try:
            # Create the output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save the transcription to the specified output path
            async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
                await f.write(transcription_text)

            if video_id:
                log_success_by_video_id(self.logger, video_id, "Transcription saved to: %s", output_path)
            return output_path
        except Exception as e:
            if video_id:
                log_error_by_video_id(self.logger, video_id, "Failed to save transcription to %s: %s", output_path, e)
            return None

    async def transcribe_audio_and_save(self, audio_path: Path, output_path: Path, chunk_length_ms: int = AUDIO_CHUNK_LENGTH_MS, video_id: str = None) -> Optional[Path]:
        """
        Transcribes audio and saves the result to a file.

        Args:
            audio_path (Path): The path to the audio file to transcribe.
            output_path (Path): The path where the transcription should be saved.
            chunk_length_ms (int): The length of each chunk in milliseconds.
            video_id (str, optional): The video ID for logging purposes.

        Returns:
            Optional[Path]: Path to the saved transcription file, or None if operation failed.
        """
        # Transcribe the audio
        transcription_text = await self.transcribe_audio(audio_path, chunk_length_ms, video_id)

        if not transcription_text:
            return None

        # Save transcription to file using the separate function
        return await self._save_transcription_to_file(transcription_text, output_path, video_id)