import os
import speech_recognition as sr
# from vosk import Model, KaldiRecognizer
from moviepy.editor import VideoFileClip
import wave
import sounddevice as sd
from pydub import AudioSegment

class AudioTranscriber:
    def __init__(self, audio_path, logger):
        """
        After a lot of trial and error this is the only function that worked for me.
        """
        self.logger = logger
        self.transcription = self.chunk_and_transcribe_audio_with_speechrecognition(audio_path, 10000)

    def chunk_and_transcribe_audio_with_speechrecognition(self, audio_path, chunk_length_in_millis):
        """
        Transcribing a full length audio file does not work for some reason. Chunking the audio to smaller parts works.

        :return: The entire transcription of all the combined chunks transcriptions.
        """

        recognizer = sr.Recognizer()
        full_audio = AudioSegment.from_file(audio_path)
        audio_length = len(full_audio)
        total_transcription = ''
        start_time = 0
        end_time = chunk_length_in_millis
        transcribed_chunks = []

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
                text = recognizer.recognize_google(audio)
                transcribed_chunks.append(text)
            except sr.UnknownValueError:
                self.logger.warning(f"Chunk {chunk_index}: Google Speech Recognition could not understand audio.")
                text = "[unintelligible] "
                transcribed_chunks.append(text)
            except sr.RequestError as e:
                self.logger.error(f"Chunk {chunk_index}: Could not request results from Google Speech Recognition service; {e}")
                text = f"[request error: {e}] "
                transcribed_chunks.append(text)
            except Exception as e:
                self.logger.error(f"An unexpected error occurred during transcription of chunk {chunk_index}: {e}")
                text = "[unexpected transcription error] "
                transcribed_chunks.append(text)
            finally:
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)
                self.logger.info(f"Chunk {chunk_index} Text: {text}")

            start_time += chunk_length_in_millis
            end_time += chunk_length_in_millis
            if end_time > audio_length:
                end_time = audio_length

        return " ".join(transcribed_chunks)

    def generate_audio_transcription_speechrecognition(self, audio_path):
        recognizer = sr.Recognizer()

        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)  # Record the entire audio file

        try:
            text = recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Google Speech Recognition could not understand audio"
        except sr.RequestError as e:
            return "Could not request results from Google Speech Recognition service; {0}".format(e)

    def transcribe_microphone_with_speechrecognition(self, duration=10):
        recognizer = sr.Recognizer()

        duration = duration  # seconds
        fs = 44100  # Sample rate
        my_recording = sd.rec(int(duration * fs), samplerate=fs, channels=2, dtype='int16')
        sd.wait()

        tem_wav_file_name = 'recording.wav'
        with wave.open(tem_wav_file_name, 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)  # 2 bytes = 16 bits
            wf.setframerate(fs)
            wf.writeframes(my_recording.tobytes())
        print('done recording')

        with sr.AudioFile(tem_wav_file_name) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)

        os.remove(tem_wav_file_name)
        return text

    def generate_audio_transcription_vosk(self, audio_path, number_of_chunks=300):
        """
        Vosk has difficulties apparently with large data so chunking it should solve the problem.

        :return: audio transcription.
        """

        model_path = './vosk-model-small-en-us-0.15'
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)

        wf = wave.open(audio_path, "rb")

        total_data_length = wf.getnframes() * wf._framesize
        chunk_size = total_data_length // number_of_chunks  # Adjust as needed
        print(chunk_size)

        processed_frames = 0
        while True:
            data = wf.readframes(chunk_size)
            if len(data) == 0:
                break

            if recognizer.AcceptWaveform(data):
                print(recognizer.Result())

            processed_frames += len(data)
            progress = min((processed_frames / total_data_length) * 100, 100)
            self.logger.info(f'Progress: {progress:.2f}%', end='')

        print("Processing complete.")
        return recognizer.FinalResult()


class AudioExtractor:
    def __init__(self, video_path, audio_path, logger):
        self.logger = logger
        self.extract_audio_as_wav(video_path, audio_path)

    def extract_audio_as_wav(self, video_path, audio_path):
        output_dir = os.path.dirname(audio_path)
        os.makedirs(output_dir, exist_ok=True)
        try:
            video = VideoFileClip(video_path)
            audio = video.audio
            audio.write_audiofile(audio_path)
            self.logger.info(f"Audio extracted successfully from {video_path} to {audio_path}")
        except Exception as e:
            self.logger.error(f"Error extracting audio from {video_path}: {e}")