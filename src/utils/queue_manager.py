"""
Message queue abstraction layer for consistent operations across services.
"""
from typing import Dict, Any


class QueueManager:
    """
    Provides a consistent interface for message queue operations across services.
    """
    def __init__(self, logger):
        self.logger = logger
        from src.utils.queue_client import QueueClient
        self.client = QueueClient(logger=logger)

    def declare_queue(self, queue_name: str):
        """Declare a queue if it doesn't exist."""
        self.client.declare_queue(queue_name)

    def send_message(self, queue_name: str, message: Dict[str, Any], video_id: str = None) -> bool:
        """
        Send a message to a queue.
        Handles its own logging for success and failure.
        Returns True if successful, False otherwise.
        """
        try:
            self.client.declare_queue(queue_name)
            self.client.publish_message(queue_name, message)
            if video_id:
                self.logger.info("[%s] Published message to queue '%s'", video_id, queue_name)
            else:
                self.logger.info("Published message to queue '%s'", queue_name)
            return True
        except Exception as e:
            if video_id:
                self.logger.error("[%s] Failed to publish message to queue '%s': %s", video_id, queue_name, e)
            else:
                self.logger.error("Failed to publish message to queue '%s': %s", queue_name, e)
            return False

    def close(self):
        """Close the queue client connection."""
        self.client.close_connection()