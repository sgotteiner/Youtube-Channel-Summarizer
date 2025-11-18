"""
Constants for database and server connections.
"""

# Default database connection parameters
DEFAULT_POSTGRES_USER = "user1"
DEFAULT_POSTGRES_PASSWORD = "password1"
DEFAULT_POSTGRES_HOST = "postgres"
DEFAULT_POSTGRES_PORT = "5432"
DEFAULT_POSTGRES_DB = "youtube_summarizer"

# Default MongoDB connection parameters
DEFAULT_MONGO_HOST = "mongo"
DEFAULT_MONGO_PORT = "27017"

# Default RabbitMQ connection parameters
DEFAULT_RABBITMQ_HOST = "rabbitmq"
DEFAULT_RABBITMQ_PORT = "5672"

# Default Kafka connection parameters
DEFAULT_KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"
DEFAULT_KAFKA_HOST = "kafka"
DEFAULT_KAFKA_PORT = "29092"

# Default API server settings
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 5000