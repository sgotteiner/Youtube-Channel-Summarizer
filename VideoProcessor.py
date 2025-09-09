import os
import re
from pathlib import Path
import logging
from ChannelVideoDownloader import VideoDownloader
from AudioTranscriber import AudioTranscriber, AudioExtractor
from AgentSummarizer import OpenAISummarizerAgent
from yt_dlp import YoutubeDL

class VideoProcessor:
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

        self.sanitized_video_title = self._sanitize_filename(self.video_title)
        self.base_filename = f"{self.sanitized_video_title}-{self.upload_date}"

        self._prepare_paths()

    def _sanitize_filename(self, filename: str) -> str:
        sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
        return sanitized[:100]

    def _prepare_paths(self):
        self.video_path = self.paths['videos'] / f"{self.base_filename}.mp4"
        self.audio_path = self.paths['audios'] / f"{self.base_filename}.wav"
        self.transcription_path = self.paths['transcriptions'] / f"{self.base_filename}.txt"
        self.summary_path = self.paths['summaries'] / f"{self.base_filename}.txt"

    def process(self):
        self.logger.info(f"Starting processing for video: {self.video_title} ({self.video_url})")
        if self._summary_exists():
            self.logger.info(f"Summary for {self.video_title} already exists. Skipping.")
            return

        transcription_text = self._get_transcription()
        if transcription_text:
            self._summarize_and_cleanup(transcription_text)
        else:
            self.logger.warning(f"No transcription available for {self.video_title}. Skipping summarization.")
        self.logger.info(f"Finished processing for video: {self.video_title}")

    def _summary_exists(self) -> bool:
        return self.summary_path.exists()

    def _get_transcription(self) -> str | None:
        if self.transcription_path.exists():
            self.logger.info(f"Transcription for {self.video_title} already exists. Reading from file.")
            return self.transcription_path.read_text(encoding="utf-8")

        if self.has_captions:
            self.logger.info(f"Attempting to download captions for {self.video_title}.")
            transcription = self._download_captions()
            if transcription:
                return transcription

        return self._transcribe_audio()

    def _download_captions(self) -> str | None:
        # This logic is complex and might be better in its own class in a future refactoring
        ydl_opts = {
            "skip_download": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "quiet": True,
            "outtmpl": str(self.transcription_path.parent / self.video_id) + ".%(ext)s",
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
            self.logger.error(f"Error during subtitle download for {self.video_title}: {e}")
        return None

    def _process_vtt_file(self, vtt_path: Path) -> str:
        lines = vtt_path.read_text(encoding="utf-8").splitlines()
        cleaned_lines = [
            line.strip() for line in lines 
            if "-->" not in line and not line.startswith(("WEBVTT", "Kind:", "Language:")) and line.strip()
        ]
        return " ".join(cleaned_lines)

    def _transcribe_audio(self) -> str | None:
        video_downloader: VideoDownloader = self.services['video_downloader']
        audio_extractor: AudioExtractor = self.services['audio_extractor']
        audio_transcriber: AudioTranscriber = self.services['audio_transcriber']

        if not self.video_path.exists():
            video_downloader.download_video(self.video_url, self.video_title, self.upload_date, self.paths['videos'])
        
        if not self.video_path.exists():
            self.logger.error(f"Video download failed for {self.video_title}. Cannot transcribe.")
            return None

        if not self.audio_path.exists():
            audio_extractor.extract_audio(self.video_path, self.audio_path)

        if not self.audio_path.exists():
            self.logger.error(f"Audio extraction failed for {self.video_title}. Cannot transcribe.")
            return None
            
        transcription = audio_transcriber.transcribe_audio(self.audio_path)
        if transcription:
            self.transcription_path.write_text(transcription, encoding="utf-8")
        return transcription

    def _summarize_and_cleanup(self, transcription_text: str):
        summarizer: OpenAISummarizerAgent = self.services['summarizer']
        
        self._handle_experimental_summary(summarizer.is_openai_runtime)

        if not self.summary_path.exists():
            self.logger.info(f"Starting summarization for {self.video_title}...")
            summary = summarizer.summary_call(transcription_text)
            if summary:
                self.summary_path.write_text(summary, encoding="utf-8")
                self.logger.info(f"Summarization complete for {self.video_title}.")
                if self.is_save_only_summaries:
                    self._cleanup_intermediate_files()
            else:
                self.logger.error(f"Summarization failed for {self.video_title}.")

    def _handle_experimental_summary(self, is_openai_runtime: bool):
        experimental_summary_path = self.paths['summaries'].parent / 'experimental' / self.summary_path.name
        if is_openai_runtime and experimental_summary_path.exists():
            self.logger.info(f"OpenAI runtime is ON. Deleting existing experimental summary for {self.video_title}.")
            try:
                os.remove(experimental_summary_path)
                if not any(experimental_summary_path.parent.iterdir()):
                    os.rmdir(experimental_summary_path.parent)
            except Exception as e:
                self.logger.error(f"Error deleting experimental summary {experimental_summary_path}: {e}")

    def _cleanup_intermediate_files(self):
        self.logger.info(f"Deleting intermediate files for {self.video_title}.")
        for file_path in [self.video_path, self.audio_path, self.transcription_path]:
            if file_path.exists():
                try:
                    os.remove(file_path)
                    self.logger.info(f"Deleted: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error deleting {file_path}: {e}")
