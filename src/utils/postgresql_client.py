import os
from sqlalchemy import create_engine, Column, String, Float, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
import logging

logger = logging.getLogger(__name__)

# Define an enum for the processing status
class VideoStatus(enum.Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    AUDIO_EXTRACTING = "AUDIO_EXTRACTING"
    AUDIO_EXTRACTED = "AUDIO_EXTRACTED"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    SUMMARIZING = "SUMMARIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

Base = declarative_base()

class Video(Base):
    __tablename__ = 'videos'

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False, index=True)
    channel_name = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    upload_date = Column(String) # Keep as string to match existing data
    duration = Column(Float)
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING, nullable=False, index=True)
    video_file_path = Column(String)
    audio_file_path = Column(String)
    working_file_path = Column(String)

    def __repr__(self):
        return f"<Video(id='{self.id}', title='{self.title}', status='{self.status}')>"


class PostgresClient:
    def __init__(self, db_url=None):
        if db_url is None:
            db_url = os.environ.get("POSTGRES_URL", "postgresql://user1:password1@postgres:5432/youtube_summarizer")

        # Configure the engine with connection pooling and proper disposal
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,  # Validates connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=False,          # Set to True for SQL debugging
            connect_args={
                "connect_timeout": 10,  # Timeout for connections
            }
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.create_tables()

    def create_tables(self):
        try:
            # Create tables first
            Base.metadata.create_all(bind=self.engine)

            # Update schema with any missing columns or enum values
            self._update_schema()

            logger.info("PostgreSQL tables created/updated successfully.")
        except Exception as e:
            logger.error(f"Error creating PostgreSQL tables: {e}")

    def _update_schema(self):
        """Add missing columns and enum values to the database schema."""
        from sqlalchemy import text
        try:
            with self.engine.connect() as conn:
                # Add missing enum values
                try:
                    conn.execute(text("ALTER TYPE videostatus ADD VALUE IF NOT EXISTS 'AUDIO_EXTRACTING';"))
                except Exception:
                    # If the enum value already exists or database doesn't support this syntax
                    pass

                # Add missing columns if they don't exist
                try:
                    # Check if working_file_path column exists
                    result = conn.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='videos' AND column_name='working_file_path'
                    """))
                    exists = result.fetchone() is not None
                    
                    if not exists:
                        conn.execute(text("ALTER TABLE videos ADD COLUMN working_file_path VARCHAR;"))
                        logger.info("Added working_file_path column to videos table")
                except Exception as e:
                    logger.warning(f"Could not update schema (working_file_path): {e}")

                # Commit the transaction
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not update database schema: {e}")
            # This is not critical for basic functionality, just log and continue

    def get_session(self):
        return self.SessionLocal()


postgres_client = PostgresClient()