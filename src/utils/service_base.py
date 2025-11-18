"""
Abstract base class for all services to handle common functionality.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.utils.logger import setup_logging
from src.utils.postgresql_client import postgres_client, Video
from src.utils.queue_client import QueueClient
from src.utils.event_publisher import EventPublisher
from src.utils.kafka_producer import KafkaEventProducer
from src.enums.service_enums import ProcessingStatus


class ServiceBase(ABC):
    """
    Base class for all services providing common functionality like
    database connections, queue clients, event publishers, and error handling.
    """
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.logger = setup_logging()
        self.db = postgres_client
        self.queue_client = None
        self.event_publisher = None
        self.kafka_producer = None
        self.loop = asyncio.get_event_loop()

    async def initialize(self):
        """Initialize all service components."""
        self.queue_client = QueueClient(logger=self.logger)
        self.event_publisher = EventPublisher(logger=self.logger)
        self.kafka_producer = KafkaEventProducer(logger=self.logger)
        self.queue_client.declare_queue(self.queue_name)

    async def cleanup(self):
        """Clean up all service connections."""
        if self.queue_client:
            self.queue_client.close_connection()
        if self.event_publisher:
            self.event_publisher.close()
        if self.kafka_producer:
            self.kafka_producer.close()

    async def update_video_status(self, video_id: str, status: ProcessingStatus, 
                                  audio_file_path: Optional[str] = None, 
                                  video_file_path: Optional[str] = None):
        """Update video status in the database."""
        session = self.db.get_session()
        try:
            video = session.query(Video).filter_by(id=video_id).first()
            if not video:
                self.logger.error(f"[{video_id}] Video not found in database")
                return False
            
            video.status = status
            if audio_file_path:
                video.audio_file_path = audio_file_path
            if video_file_path:
                video.video_file_path = video_file_path
            
            session.commit()
            self.logger.info(f"[{video_id}] Database status updated to {status} in PostgreSQL")
            return True
        except Exception as e:
            self.logger.error(f"[{video_id}] Error updating video status: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    async def publish_message(self, queue_name: str, message: Dict[str, Any]):
        """Publish a message to a queue."""
        try:
            self.queue_client.declare_queue(queue_name)
            self.queue_client.publish_message(queue_name, message)
            self.logger.info(f"Published message to queue '{queue_name}': {message}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to publish message to queue '{queue_name}': {e}")
            return False

    async def publish_event(self, event_type: str, event_payload: Dict[str, Any]):
        """Publish an event to both RabbitMQ exchange and Kafka."""
        success_rabbitmq = False
        success_kafka = False
        
        try:
            # Publish to RabbitMQ exchange
            self.event_publisher.publish(event_type, event_payload)
            success_rabbitmq = True
        except Exception as e:
            self.logger.error(f"Failed to publish event '{event_type}' to RabbitMQ: {e}")
        
        try:
            # Publish to Kafka
            self.kafka_producer.send_event(event_type, event_payload)
            success_kafka = True
        except Exception as e:
            self.logger.error(f"Failed to publish event '{event_type}' to Kafka: {e}")
        
        return success_rabbitmq or success_kafka

    @abstractmethod
    async def process_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Process a single task. Return True if successful, False otherwise.
        This method must be implemented by subclasses.
        """
        pass

    async def run(self):
        """Run the service continuously."""
        await self.initialize()
        try:
            self.logger.info(f"Starting {self.__class__.__name__} to consume from queue '{self.queue_name}'")
            await self._consume_messages()
        finally:
            await self.cleanup()

    async def _consume_messages(self):
        """
        Consume messages from the queue and process them using async/await.
        This is the core message processing loop.
        """
        # Since pika is sync, we'll need to run the consumer in a thread
        # But eventually, we should move to an async RabbitMQ client like aio-pika
        self.logger.error("This requires an async RabbitMQ client implementation. "
                         "The current implementation will still require threading.")