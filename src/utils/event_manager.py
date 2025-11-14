"""
Event publishing abstraction layer for consistent operations across services.
"""
from typing import Dict, Any


class EventManager:
    """
    Provides a consistent interface for event publishing across services.
    Publishes to both RabbitMQ exchange and Kafka.
    """
    def __init__(self, logger):
        self.logger = logger
        from src.utils.event_publisher import EventPublisher
        from src.utils.kafka_producer import KafkaEventProducer
        self.rabbitmq_publisher = EventPublisher(logger=logger)
        self.kafka_producer = KafkaEventProducer(logger=logger)

    def publish_event(self, event_type: str, event_payload: Dict[str, Any], video_id: str = None) -> bool:
        """
        Publish an event to both RabbitMQ exchange and Kafka.
        Handles its own logging for success and failure.
        Returns True if at least one publishing succeeded, False otherwise.
        """
        success_rabbitmq = False
        success_kafka = False
        video_prefix = f"[{video_id}] " if video_id else ""

        try:
            # Publish to RabbitMQ exchange
            self.rabbitmq_publisher.publish(event_type, event_payload)
            success_rabbitmq = True
        except Exception as e:
            self.logger.error("%sFailed to publish event '%s' to RabbitMQ: %s", video_prefix, event_type, e)

        try:
            # Publish to Kafka
            self.kafka_producer.send_event(event_type.lower().replace(' ', '_'), event_payload)
            success_kafka = True
        except Exception as e:
            self.logger.error("%sFailed to publish event '%s' to Kafka: %s", video_prefix, event_type, e)

        # Return True if at least one succeeded
        result = success_rabbitmq or success_kafka

        if result and video_id:
            self.logger.info("[%s] Successfully published event '%s'", video_id, event_type)
        elif not result and video_id:
            self.logger.error("[%s] Failed to publish event '%s' to any system", video_id, event_type)

        return result

    def close(self):
        """Close all event publishing connections."""
        try:
            self.rabbitmq_publisher.close()
        except Exception as e:
            self.logger.warning("Error closing RabbitMQ publisher: %s", e)

        try:
            self.kafka_producer.close()
        except Exception as e:
            self.logger.warning("Error closing Kafka producer: %s", e)