"""
Module for audio transcription and extraction from videos.
"""

import os
import speech_recognition as sr
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pathlib import Path

class AudioTranscriber:
    def __init__(self, logger):
        """
        Initialize the AudioTranscriber.
        
        :param logger: Logger for logging messages
        """
        self.logger = logger

    def transcribe_audio(self, audio_path: Path, chunk_length_in_millis: int = 10000) -> str | None:
        """
        Transcribe audio by chunking it into smaller parts.
        
        Transcribing a full length audio file does not work for some reason. 
        Chunking the audio to smaller parts works.

        :param audio_path: Path to the audio file
        :param chunk_length_in_millis: Length of each chunk in milliseconds
        :return: The entire transcription of all the combined chunks or None if an error occurred
        """
        if not audio_path.exists():
            self.logger.error(f"Audio file not found for transcription: {audio_path}")
            return None

        recognizer = sr.Recognizer()
        full_audio = AudioSegment.from_file(audio_path)
        audio_length = len(full_audio)
        total_transcription = ''
        start_time = 0
        end_time = chunk_length_in_millis
        transcribed_chunks = []

        self.logger.info(f"Starting audio transcription for {audio_path}...")

        while start_time < audio_length:
            chunk_index = start_time // chunk_length_in_millis
            chunk_filename = f"chunk_{chunk_index}.wav"
            text = ""

            try:
                chunk = full_audio[start_time:end_time]
                chunk.export(chunk_filename, format="wav")
                audio_data = sr.AudioFile(chunk_filename)
                with audio_data as source:
                    audio = recognizer.record(source)
                text = recognizer.recognize_google(audio) + '\n'
                transcribed_chunks.append(text)
            except sr.UnknownValueError:
                self.logger.warning(f"Chunk {chunk_index}: Google Speech Recognition could not understand audio.")
                text = "[unintelligible]\n"
                transcribed_chunks.append(text)
            except sr.RequestError as e:
                self.logger.error(f"Chunk {chunk_index}: Could not request results from Google Speech Recognition service; {e}")
                text = f"[request error: {e}]\n"
                transcribed_chunks.append(text)
            except Exception as e:
                self.logger.error(f"An unexpected error occurred during transcription of chunk {chunk_index}: {e}")
                text = "[unexpected transcription error]\n"
                transcribed_chunks.append(text)
            finally:
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)
                self.logger.debug(f"Chunk {chunk_index} Text: {text}") # Changed to debug for less verbose logging

            start_time += chunk_length_in_millis
            end_time += chunk_length_in_millis
            if end_time > audio_length:
                end_time = audio_length

        self.logger.info(f"Audio transcription finished for {audio_path}.")
        return " ".join(transcribed_chunks)


class AudioExtractor:
    def __init__(self, logger):
        self.logger = logger

    def extract_audio(self, video_path: Path, audio_path: Path) -> bool:
        """
        Extracts audio from a video file and saves it as a WAV file.
        
        :param video_path: Path to the video file
        :param audio_path: Path to save the extracted audio file
        :return: True if audio was extracted or already exists, False otherwise
        """
        if audio_path.exists():
            self.logger.info(f"Audio for {video_path} already exists at {audio_path}. Skipping extraction.")
            return True

        output_dir = audio_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.logger.info(f"Starting audio extraction from {video_path} to {audio_path}...")
            video = VideoFileClip(str(video_path))
            audio = video.audio
            audio.write_audiofile(str(audio_path))
            self.logger.info(f"Audio extracted successfully from {video_path} to {audio_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error extracting audio from {video_path}: {e}")
            return False