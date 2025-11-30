import os
from sqlalchemy import create_engine, Column, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
from src.constants.time_constants import DB_POOL_RECYCLE_SECONDS, POSTGRES_CONNECT_TIMEOUT
from src.constants.connection_constants import (
    DEFAULT_POSTGRES_USER,
    DEFAULT_POSTGRES_PASSWORD,
    DEFAULT_POSTGRES_HOST,
    DEFAULT_POSTGRES_PORT,
    DEFAULT_POSTGRES_DB
)
from src.enums.service_enums import ServiceType, ProcessingStatus

logger = logging.getLogger(__name__)

Base = declarative_base()

class Video(Base):
    __tablename__ = 'videos'

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False, index=True)
    channel_name = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    upload_date = Column(String) # Keep as string to match existing data
    duration = Column(Float)
    has_captions = Column(Boolean, default=False, nullable=False)  # Whether the video has captions available
    stage = Column(String, default=ServiceType.DISCOVERY.name, nullable=False, index=True)  # Tracks which service is currently handling the video
    status = Column(String, default=ProcessingStatus.PROCESSING.value, nullable=False, index=True)  # Tracks the processing status (PROCESSING, COMPLETED, FAILED)

    def __repr__(self):
        return f"<Video(id='{self.id}', title='{self.title}', status='{self.status}')>"


class PostgresClient:
    def __init__(self, db_url=None):
        if db_url is None:
            # Build the database URL from individual environment variables with sensible defaults
            user = os.getenv('POSTGRES_USER', DEFAULT_POSTGRES_USER)
            password = os.getenv('POSTGRES_PASSWORD', DEFAULT_POSTGRES_PASSWORD)
            host = os.getenv('POSTGRES_HOST', DEFAULT_POSTGRES_HOST)
            port = os.getenv('POSTGRES_PORT', DEFAULT_POSTGRES_PORT)
            db_name = os.getenv('POSTGRES_DB', DEFAULT_POSTGRES_DB)
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

        # Configure the engine with connection pooling and proper disposal
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,  # Validates connections before use
            pool_recycle=DB_POOL_RECYCLE_SECONDS,   # Recycle connections after 1 hour
            echo=False,          # Set to True for SQL debugging
            connect_args={
                "connect_timeout": POSTGRES_CONNECT_TIMEOUT,  # Timeout for connections
            }
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.create_tables()

    def create_tables(self):
        try:
            # Create tables first
            Base.metadata.create_all(bind=self.engine)

            logger.info("PostgreSQL tables created successfully.")
        except Exception as e:
            logger.error(f"Error creating PostgreSQL tables: {e}")


    def get_session(self):
        return self.SessionLocal()


postgres_client = PostgresClient()