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

    def _transcribe_chunk_sync(self, chunk_filename: str, chunk_index: int) -> str:
        """
        Transcribes a single audio chunk using Google Speech Recognition.

        Args:
            chunk_filename (str): The filename of the audio chunk to transcribe.
            chunk_index (int): The index of the chunk, for logging purposes.

        Returns:
            str: The transcribed text, or an error/unintelligible message.
        """
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

    async def transcribe_audio(self, audio_path: Path, chunk_length_ms: int = 10000, video_id: str = None) -> Optional[str]:
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
        if not audio_path.exists():
            self.logger.error(f"Audio file not found for transcription: {audio_path}")
            return None

        full_audio = AudioSegment.from_file(audio_path)
        self.logger.info(f"Starting audio transcription for {audio_path}...")

        # Create unique chunk filenames to avoid race conditions when multiple videos are being processed
        audio_file_prefix = audio_path.stem.replace(" ", "_").replace("-", "_")  # Sanitize filename
        chunk_base_name = f"{audio_file_prefix}_{video_id}" if video_id else audio_file_prefix

        # Prepare chunks
        chunks_info = []
        for i, start_ms in enumerate(range(0, len(full_audio), chunk_length_ms)):
            end_ms = start_ms + chunk_length_ms
            chunk = full_audio[start_ms:end_ms]
            chunk_filename = f"{chunk_base_name}_chunk_{i}.wav"
            chunks_info.append((chunk, chunk_filename, i))

        # Process chunks concurrently
        self.logger.info(f"Starting to process {len(chunks_info)} audio chunks concurrently...")

        # Export all chunks to temporary files first
        loop = asyncio.get_event_loop()
        for chunk, chunk_filename, i in chunks_info:
            chunk.export(chunk_filename, format="wav")

        # Process transcriptions concurrently
        tasks = []
        for _, chunk_filename, chunk_index in chunks_info:
            task = loop.run_in_executor(self.executor, self._transcribe_chunk_sync, chunk_filename, chunk_index)
            tasks.append(task)

        transcribed_chunks = await asyncio.gather(*tasks, return_exceptions=True)

        # Clean up temporary files after processing
        for _, chunk_filename, _ in chunks_info:
            try:
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)
            except Exception as e:
                self.logger.warning(f"Could not remove temporary file {chunk_filename}: {e}")

        # Handle any exceptions during transcription
        final_chunks = []
        for i, chunk_result in enumerate(transcribed_chunks):
            if isinstance(chunk_result, Exception):
                self.logger.error(f"Error processing chunk {i}: {chunk_result}")
                final_chunks.append("[transcription error]\n")
            else:
                final_chunks.append(chunk_result)

        transcription_result = " ".join(final_chunks)
        self.logger.info(f"Audio transcription finished for {audio_path}. Combined {len([t for t in final_chunks if t.strip() and '[transcription error]' not in t])} successful chunks.")

        # Automatically log completion status with video_id if provided
        if video_id:
            if transcription_result:
                self.logger.info("[%s] Transcription completed (length: %d characters)", video_id, len(transcription_result))

        return transcription_result

    async def transcribe_audio_and_save(self, audio_path: Path, output_path: Path, chunk_length_ms: int = 10000, video_id: str = None) -> Optional[Path]:
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

        try:
            # Create the output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save the transcription to the specified output path
            async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
                await f.write(transcription_text)

            self.logger.info("[%s] Transcription saved to: %s", video_id, output_path)
            return output_path
        except Exception as e:
            self.logger.error("[%s] Failed to save transcription to %s: %s", video_id, output_path, e)
            return None