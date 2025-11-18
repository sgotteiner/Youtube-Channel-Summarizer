import os
from pymongo import MongoClient
import logging
from src.constants.service_constants import MONGO_URL_ENV, DEFAULT_MONGO_URL, APP_NAME

logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self, db_url=None, db_name=APP_NAME):  # Default name, but can be configured
        # Use Docker service name if no URL provided
        if db_url is None:
            db_url = os.environ.get(MONGO_URL_ENV, DEFAULT_MONGO_URL)
        
        try:
            self.client = MongoClient(db_url)
            self.db = self.client[db_name]
            self.transcriptions = self.db.transcriptions
            self.summaries = self.db.summaries
            logger.info("Successfully connected to MongoDB.")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")

    def close(self):
        self.client.close()

# Create a single instance for use in your services
mongodb_client = MongoDBClient()
