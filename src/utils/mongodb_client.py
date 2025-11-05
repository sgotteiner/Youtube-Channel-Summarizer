import os
from pymongo import MongoClient
import logging

logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self, db_url=None, db_name='youtube_summarizer'):
        # Use Docker service name if no URL provided
        if db_url is None:
            db_url = os.environ.get("MONGO_URL", "mongodb://mongo:27017/")
        
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
