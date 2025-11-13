import os
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DisconnectionError, OperationalError
import enum
import logging

logger = logging.getLogger(__name__)

# Define an enum for the processing status
class VideoStatus(enum.Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
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
            Base.metadata.create_all(bind=self.engine)
            logger.info("PostgreSQL tables created successfully (if they didn't exist).")
        except Exception as e:
            logger.error(f"Error creating PostgreSQL tables: {e}")

    def get_session(self):
        return self.SessionLocal()

postgres_client = PostgresClient()
