"""
Handles file system operations for the YouTube Channel Summarizer.

This class is responsible for generating standardized filenames and checking for
the existence of files, particularly summaries. This centralizes file management
logic and ensures consistency across the application.
"""
import os
import re
from pathlib import Path
from typing import Dict

class FileManager:
    """
    Manages file naming conventions, directory structures, and checks for existing files.
    """
    def __init__(self, channel_id: str, is_openai_runtime: bool, logger):
        """
        Initializes the FileManager and creates the necessary directory structure.

        Args:
            channel_id (str): The ID of the YouTube channel.
            is_openai_runtime (bool): Flag to determine if experimental directories should be used.
            logger: The logger instance for logging messages.
        """
        self.channel_id = channel_id
        self.paths = self._setup_directories(channel_id, is_openai_runtime)
        self.summaries_dir = self.paths['summaries']
        self.logger = logger

    def _setup_directories(self, channel_id: str, is_openai_runtime: bool) -> Dict[str, Path]:
        """Creates and returns paths for the required directories."""
        base_paths = {
            'videos': Path(f'./data/channel_videos/{channel_id}'),
            'audios': Path(f'./data/channel_audios/{channel_id}'),
            'transcriptions': Path(f'./data/channel_transcriptions/{channel_id}'),
            'summaries': Path(f'./data/channel_summaries/{channel_id}'),
        }
        for path in base_paths.values():
            path.mkdir(parents=True, exist_ok=True)

        if not is_openai_runtime:
            summaries_path = base_paths['summaries'] / 'experimental'
            summaries_path.mkdir(parents=True, exist_ok=True)
            base_paths['summaries'] = summaries_path
        
        return base_paths

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Removes invalid characters from a string to make it a valid filename."""
        sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
        return sanitized[:100]

    @staticmethod
    def get_base_filename(video_data: Dict) -> str:
        """
        Generates the standardized base filename using the 'name-date-id' format.

        Args:
            video_data (Dict): A dictionary containing video metadata. Must include
                               'video_title', 'upload_date', and 'video_id'.

        Returns:
            str: The standardized base filename without the extension.
        """
        sanitized_title = FileManager._sanitize_filename(video_data["video_title"])
        return f"{sanitized_title}-{video_data['upload_date']}-{video_data['video_id']}"

    def get_video_paths(self, video_data: Dict) -> Dict[str, Path]:
        """
        Constructs a dictionary of all required file paths for a single video.

        Args:
            video_data (Dict): A dictionary containing the video's metadata.

        Returns:
            Dict[str, Path]: A dictionary mapping path types to their full Path objects.
        """
        base_filename = self.get_base_filename(video_data)
        return {
            "video": self.paths['videos'] / f"{base_filename}.mp4",
            "audio": self.paths['audios'] / f"{base_filename}.wav",
            "transcription": self.paths['transcriptions'] / f"{base_filename}.txt",
            "summary": self.paths['summaries'] / f"{base_filename}.txt",
        }

    def does_summary_exist(self, video_id: str) -> bool:
        """
        Checks if a summary file for a given video ID already exists.
        This is efficient as it uses a glob pattern and does not require the full filename.

        Args:
            video_id (str): The unique ID of the video.

        Returns:
            bool: True if a summary file for the video exists, False otherwise.
        """
        pattern = f"*-{video_id}.txt"
        return any(self.summaries_dir.glob(pattern))

    def cleanup_intermediate_files(self, video_paths: Dict[str, Path]):
        """
        Deletes the video, audio, and transcription files for a video.

        Args:
            video_paths (Dict[str, Path]): A dictionary containing the paths to the video's files.
        """
        # We don't want to delete the summary, so we exclude it from the list of files to delete.
        for file_type, file_path in video_paths.items():
            if file_type == "summary":
                continue
            
            if file_path.exists():
                try:
                    os.remove(file_path)
                    self.logger.info(f"Deleted intermediate file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error deleting file {file_path}: {e}")

