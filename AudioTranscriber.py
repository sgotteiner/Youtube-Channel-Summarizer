"""
Module for audio transcription and extraction from videos.
"""

import os
import speech_recognition as sr
from moviepy.editor import VideoFileClip
import wave
import sounddevice as sd
from pydub import AudioSegment
from typing import Optional

# Optional Vosk import - only imported if needed
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


class AudioTranscriber:
    """Handles transcription of audio files using various methods."""

    def __init__(self, audio_path: str):
        """
        Initialize the AudioTranscriber and start the transcription process.
        
        :param audio_path: Path to the audio file to transcribe
        """
        self.transcription = self.chunk_and_transcribe_audio_with_speechrecognition(audio_path, 10000)

    def chunk_and_transcribe_audio_with_speechrecognition(self, audio_path: str, chunk_length_in_millis: int) -> str:
        """
        Transcribe audio by chunking it into smaller parts.
        
        Transcribing a full length audio file does not work for some reason. 
        Chunking the audio to smaller parts works.

        :param audio_path: Path to the audio file
        :param chunk_length_in_millis: Length of each chunk in milliseconds
        :return: The entire transcription of all the combined chunks
        """
        recognizer = sr.Recognizer()
        full_audio = AudioSegment.from_file(audio_path)
        audio_length = len(full_audio)
        total_transcription = ''
        start_time = 0
        end_time = chunk_length_in_millis

        while start_time < audio_length:
            chunk_index = start_time // chunk_length_in_millis
            chunk_filename = "chunk.wav"

            try:
                chunk = full_audio[start_time:end_time]
                chunk.export(chunk_filename, format="wav")
            except Exception as e:
                print(f"Error exporting chunk {chunk_index}: {start_time}, {end_time}, {e}")

            audio_data = sr.AudioFile(chunk_filename)
            with audio_data as source:
                audio = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio)
                total_transcription += text
                print(f"Chunk {chunk_index} Text: {text}")
            except Exception as e:
                print(f"Error recognizing chunk {chunk_index}: {e}")
                print(f'Reached chunk {chunk_index} out of {audio_length // chunk_length_in_millis}')
                print(total_transcription)

            os.remove(chunk_filename)

            start_time += chunk_length_in_millis
            end_time += chunk_length_in_millis
            if end_time > audio_length:
                end_time = audio_length

        return total_transcription

    def generate_audio_transcription_speechrecognition(self, audio_path: str) -> str:
        """
        Transcribe audio using Google Speech Recognition.
        
        :param audio_path: Path to the audio file
        :return: Transcribed text or error message
        """
        recognizer = sr.Recognizer()

        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)  # Record the entire audio file

        try:
            text = recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Google Speech Recognition could not understand audio"
        except sr.RequestError as e:
            return f"Could not request results from Google Speech Recognition service; {e}"

    def transcribe_microphone_with_speechrecognition(self, duration: int = 10) -> str:
        """
        Transcribe audio from microphone input.
        
        :param duration: Recording duration in seconds
        :return: Transcribed text
        """
        recognizer = sr.Recognizer()
        fs = 44100  # Sample rate
        my_recording = sd.rec(int(duration * fs), samplerate=fs, channels=2, dtype='int16')
        sd.wait()

        temp_wav_file_name = 'recording.wav'
        with wave.open(temp_wav_file_name, 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)  # 2 bytes = 16 bits
            wf.setframerate(fs)
            wf.writeframes(my_recording.tobytes())
        print('Done recording')

        with sr.AudioFile(temp_wav_file_name) as source:
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio)
        os.remove(temp_wav_file_name)
        return text

    def generate_audio_transcription_vosk(self, audio_path: str, number_of_chunks: int = 300) -> Optional[str]:
        """
        Transcribe audio using Vosk offline speech recognition.
        
        Vosk has difficulties apparently with large data so chunking it should solve the problem.

        :param audio_path: Path to the audio file
        :param number_of_chunks: Number of chunks to divide the audio into
        :return: Audio transcription or None if Vosk is not available
        """
        if not VOSK_AVAILABLE:
            print("Vosk is not installed. Please install it with 'pip install vosk' to use this feature.")
            return None
            
        model_path = './vosk-model-small-en-us-0.15'
        if not os.path.exists(model_path):
            print(f"Vosk model not found at {model_path}. Please download it from https://alphacephei.com/vosk/models")
            return None
            
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)

        wf = wave.open(audio_path, "rb")

        total_data_length = wf.getnframes() * wf.getsampwidth()
        chunk_size = total_data_length // number_of_chunks  # Adjust as needed
        print(f"Chunk size: {chunk_size}")

        processed_frames = 0
        while True:
            data = wf.readframes(chunk_size)
            if len(data) == 0:
                break

            if recognizer.AcceptWaveform(data):
                print(recognizer.Result())

            processed_frames += len(data)
            progress = min((processed_frames / total_data_length) * 100, 100)
            print(f'\rProgress: {progress:.2f}%', end='')

        print("\nProcessing complete.")
        return recognizer.FinalResult()


class AudioExtractor:
    """Handles extraction of audio from video files."""

    def __init__(self, video_path: str, output_dir: str = './channel_audios/'):
        """
        Initialize the AudioExtractor and start the extraction process.
        
        :param video_path: Path to the video file
        :param output_dir: Directory where the audio file should be saved
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate audio filename from video filename
        video_filename = os.path.basename(video_path)
        audio_filename = os.path.splitext(video_filename)[0] + '.wav'
        audio_path = os.path.join(output_dir, audio_filename)
        
        self.extract_audio_as_wav(video_path, audio_path)

    def extract_audio_as_wav(self, video_path: str, audio_path: str) -> None:
        """
        Extract audio from video and save as WAV file.
        
        :param video_path: Path to the video file
        :param audio_path: Path where the audio file should be saved
        """
        video = VideoFileClip(video_path)
        audio = video.audio
        audio.write_audiofile(audio_path)