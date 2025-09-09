"""
Module for audio transcription and extraction from videos.
"""
import os
import speech_recognition as sr
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pathlib import Path
import logging
from typing import Optional

class AudioTranscriber:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.recognizer = sr.Recognizer()

    def _transcribe_chunk(self, chunk_filename: str, chunk_index: int) -> str:
        try:
            with sr.AudioFile(chunk_filename) as source:
                audio = self.recognizer.record(source)
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
        if not audio_path.exists():
            self.logger.error(f"Audio file not found for transcription: {audio_path}")
            return None

        full_audio = AudioSegment.from_file(audio_path)
        transcribed_chunks = []
        self.logger.info(f"Starting audio transcription for {audio_path}...")

        for i, start_ms in enumerate(range(0, len(full_audio), chunk_length_ms)):
            end_ms = start_ms + chunk_length_ms
            chunk = full_audio[start_ms:end_ms]
            chunk_filename = f"chunk_{i}.wav"
            
            try:
                chunk.export(chunk_filename, format="wav")
                text = self._transcribe_chunk(chunk_filename, i)
                transcribed_chunks.append(text)
            finally:
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)

        self.logger.info(f"Audio transcription finished for {audio_path}.")
        return " ".join(transcribed_chunks)

class AudioExtractor:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def extract_audio(self, video_path: Path, audio_path: Path) -> bool:
        if audio_path.exists():
            self.logger.info(f"Audio for {video_path} already exists at {audio_path}. Skipping extraction.")
            return True

        audio_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.logger.info(f"Starting audio extraction from {video_path} to {audio_path}...")
            with VideoFileClip(str(video_path)) as video:
                audio = video.audio
                audio.write_audiofile(str(audio_path))
            self.logger.info(f"Audio extracted successfully from {video_path} to {audio_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error extracting audio from {video_path}: {e}")
            return False
