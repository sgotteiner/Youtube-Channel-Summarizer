"""
Constants for the service template mappings and other static values.
"""


# Other constants
TOKEN_LIMIT = 4000
CHUNK_TARGET_SIZE = 3000





# File handling constants
MAX_FILENAME_LENGTH = 100
LOG_MAX_FILE_SIZE = 1024 * 1024  # 1 MB
LOG_BACKUP_COUNT = 5

# Exchange and queue names
EVENTS_EXCHANGE_NAME = 'events_exchange'

# Environment variable names
POSTGRES_URL_ENV = 'POSTGRES_URL'
OPENAI_API_KEY_ENV = 'OPENAI_API_KEY'

# Service host and port constants
RABBITMQ_HOST = 'rabbitmq'
KAFKA_BOOTSTRAP_SERVERS = 'kafka:29092'
MONGO_URL_ENV = 'MONGO_URL'
DEFAULT_MONGO_URL = 'mongodb://mongo:27017/'


# Configuration defaults
DEFAULT_MAX_VIDEO_LENGTH = 10

# Encoding constants
TOKENCODER_ENCODING_NAME = "cl100k_base"

# Application name
APP_NAME = "youtube_summarizer"


# File extensions
VIDEO_FILE_EXTENSION = ".mp4"
AUDIO_FILE_EXTENSION = ".wav"
TRANSCRIPTION_FILE_EXTENSION = ".txt"
CAPTION_FILE_EXTENSION = ".en.vtt"

# AI Model constants
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"