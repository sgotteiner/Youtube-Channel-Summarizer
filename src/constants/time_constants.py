"""
Constants for time and timeout values.
"""

# Async operations timeouts
ASYNC_HELPER_TIMEOUT = 5.0  # seconds

# Database timeouts
DB_POOL_RECYCLE_SECONDS = 3600  # 1 hour
POSTGRES_CONNECT_TIMEOUT = 10  # seconds

# RabbitMQ timeouts
RABBITMQ_BLOCKED_CONNECTION_TIMEOUT = 300  # seconds
RABBITMQ_SOCKET_TIMEOUT = 10  # seconds
RABBITMQ_HEARTBEAT_INTERVAL = 600  # seconds

# Kafka timeouts
KAFKA_REQUEST_TIMEOUT_MS = 15000  # 15 seconds
KAFKA_MAX_BLOCK_MS = 5000
KAFKA_RECONNECT_BACKOFF_MAX_MS = 1000
KAFKA_RECONNECT_BACKOFF_MS = 50  # Initial backoff in ms
KAFKA_SEND_TIMEOUT = 15  # seconds

# Time delays and intervals
KAFKA_CONSUMER_RETRY_DELAY = 5  # seconds
RABBITMQ_RETRY_DELAY = 5  # seconds
MONGODB_RETRY_DELAY = 5  # seconds
GENERAL_RETRY_DELAY = 5  # seconds
BACKOFF_MULTIPLIER = 2  # For exponential backoff

# Audio processing
AUDIO_CHUNK_LENGTH_MS = 10000  # 10 seconds

# API and network timeouts
DEFAULT_REQUEST_TIMEOUT = 30  # seconds