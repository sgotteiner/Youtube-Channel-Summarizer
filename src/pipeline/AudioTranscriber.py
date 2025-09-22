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

    def _transcribe_chunk(self, chunk_filename: str, chunk_index: int) -> str:
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
            return self.recognizer.recognize_google(audio) + '\n'
        except sr.UnknownValueError:
            self.logger.warning(f"Chunk {chunk_index}: Google Speech Recognition could not understand audio.")
            return "[unintelligible]\n"
        except sr.RequestError as e:
            self.logger.error(f"Chunk {chunk_index}: Could not request results from Google service; {e}")
            return f"[request error: {e}]\n"
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during transcription of chunk {chunk_index}: {e}")
            return "[unexpected transcription error]\n"

    def transcribe_audio(self, audio_path: Path, chunk_length_ms: int = 10000) -> Optional[str]:
        """
        Transcribes a full audio file by splitting it into chunks.

        This approach is necessary to handle long audio files that might otherwise
        fail with speech recognition APIs.

        Args:
            audio_path (Path): The path to the audio file.
            chunk_length_ms (int): The length of each chunk in milliseconds.

        Returns:
            Optional[str]: The full transcribed text, or None if the file doesn't exist.
        """
        if not audio_path.exists():
            self.logger.error(f"Audio file not found for transcription: {audio_path}")
            return None

        full_audio = AudioSegment.from_file(audio_path)
        transcribed_chunks = []
        self.logger.info(f"Starting audio transcription for {audio_path}...")

        # Iterate over the audio file in chunks
        for i, start_ms in enumerate(range(0, len(full_audio), chunk_length_ms)):
            end_ms = start_ms + chunk_length_ms
            chunk = full_audio[start_ms:end_ms]
            chunk_filename = f"chunk_{i}.wav"
            
            try:
                # Export chunk to a temporary file
                chunk.export(chunk_filename, format="wav")
                text = self._transcribe_chunk(chunk_filename, i)
                transcribed_chunks.append(text)
            finally:
                # Clean up the temporary chunk file
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)

        self.logger.info(f"Audio transcription finished for {audio_path}.")
        return " ".join(transcribed_chunks)
