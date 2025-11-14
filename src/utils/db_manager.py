"""
Database abstraction layer for consistent operations across services.
"""
from typing import Optional
from src.utils.postgresql_client import postgres_client, Video, VideoStatus


class DatabaseManager:
    """
    Provides a consistent interface for database operations across services.
    """
    def __init__(self, logger):
        self.client = postgres_client
        self.logger = logger

    def _log_db_info(self, video_id: str, message: str):
        """Standardized logging format for database operations."""
        self.logger.info("[%s] %s", video_id, message)

    def _log_db_error(self, video_id: str, message: str):
        """Standardized error logging format for database operations."""
        self.logger.error("[%s] %s", video_id, message)

    def get_video(self, video_id: str):
        """Get a video record from the database."""
        session = self.client.get_session()
        try:
            video = session.query(Video).filter_by(id=video_id).first()
            return video
        finally:
            session.close()

    def update_video(self, video_id: str, **fields) -> bool:
        """
        Update any fields of a video record in the database.
        Accepts any field name and value as keyword arguments.
        Returns True if successful, False otherwise.
        """
        session = self.client.get_session()
        try:
            video = session.query(Video).filter_by(id=video_id).first()
            if not video:
                self._log_db_error(video_id, "Video not found in database")
                return False

            # Update any provided fields
            for field_name, field_value in fields.items():
                if hasattr(video, field_name):
                    setattr(video, field_name, field_value)
                else:
                    self._log_db_error(video_id, f"Video model has no attribute '{field_name}'")
                    return False

            session.commit()
            field_updates = ", ".join([f"{k}={v}" for k, v in fields.items()])
            self._log_db_info(video_id, f"Database fields updated: {field_updates}")
            return True
        except Exception as e:
            self._log_db_error(video_id, f"Error updating video record: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def update_video_status(self, video_id: str, status: VideoStatus,
                           audio_file_path: Optional[str] = None,
                           video_file_path: Optional[str] = None) -> bool:
        """
        Update video status and optionally file paths in the database.
        Handles its own logging for success and failure.
        Returns True if successful, False otherwise.
        """
        updates = {"status": status}
        if audio_file_path is not None:
            updates["audio_file_path"] = audio_file_path
        if video_file_path is not None:
            updates["video_file_path"] = video_file_path
        
        return self.update_video(video_id, **updates)

    def get_videos_by_job(self, job_id: str):
        """Get all videos for a specific job."""
        session = self.client.get_session()
        try:
            videos = session.query(Video).filter(Video.job_id == job_id).all()
            return videos
        finally:
            session.close()

    def create_video_record(self, video_id: str, job_id: str, channel_name: str,
                           title: str, upload_date: str, duration: Optional[float] = None):
        """Create a new video record in the database."""
        session = self.client.get_session()
        try:
            new_video = Video(
                id=video_id,
                job_id=job_id,
                channel_name=channel_name,
                title=title,
                upload_date=upload_date,
                duration=duration,
                status=VideoStatus.PENDING
            )
            session.add(new_video)
            session.commit()
            self._log_db_info(video_id, "Video record created in database with status PENDING")
            return True
        except Exception as e:
            self._log_db_error(video_id, f"Error creating video record: {e}")
            session.rollback()
            return False
        finally:
            session.close()