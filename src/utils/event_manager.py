"""
Event publishing abstraction layer for consistent operations across services.
"""
import datetime
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

    def build_event_payload(self, video_id: str, video, result, service_specific_fields: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Build the event payload to publish when this service completes.
        """
        # Handle the case where video might be None (for discovery service)
        job_id = getattr(video, 'job_id', 'unknown') if video is not None else 'unknown'
        base_payload = {
            "video_id": video_id,
            "job_id": job_id,
            "completed_at": datetime.datetime.utcnow().isoformat()
        }

        # Add service-specific fields if provided
        if service_specific_fields:
            base_payload.update(service_specific_fields)

        return base_payload

    def get_service_specific_event_fields(self, video_id: str, video, result) -> Dict[str, Any]:
        """
        Get service-specific fields to add to the event payload.
        This can be overridden by subclasses that need specific behavior.
        """
        # Default: no additional fields
        return {}

    def _publish_event_to_rabbitmq(self, event_type: str, event_payload: Dict[str, Any]) -> bool:
        """Publish an event to RabbitMQ."""
        try:
            self.rabbitmq_publisher.publish(event_type, event_payload)
            return True
        except Exception as e:
            self.logger.error("Failed to publish event '%s' to RabbitMQ: %s", event_type, e)
            return False

    def _publish_event_to_kafka(self, event_type: str, event_payload: Dict[str, Any]) -> bool:
        """Publish an event to Kafka."""
        try:
            self.kafka_producer.send_event(event_type, event_payload)
            return True
        except Exception as e:
            self.logger.error("Failed to publish event '%s' to Kafka: %s", event_type, e)
            return False

    def publish_event(self, event_type: str, event_payload: Dict[str, Any], video_id: str = None) -> bool:
        """
        Publish an event to both RabbitMQ exchange and Kafka.
        Handles its own logging for success and failure.
        Returns True if at least one publishing succeeded, False otherwise.
        """
        success_rabbitmq = self._publish_event_to_rabbitmq(event_type, event_payload)
        success_kafka = self._publish_event_to_kafka(event_type, event_payload)

        # Return True if at least one succeeded
        result = success_rabbitmq or success_kafka

        if result and video_id:
            self.logger.info("[%s] Successfully published event '%s'", video_id, event_type)
        elif not result and video_id:
            self.logger.error("[%s] Failed to publish event '%s' to any system", video_id, event_type)

        return result

    async def publish_completion_event_async(self, event_type: str, video_id: str, video, result, service_specific_fields: Dict[str, Any] = None):
        """Async version to publish completion events."""
        event_payload = self.build_event_payload(video_id, video, result, service_specific_fields)
        return self.publish_event(event_type, event_payload, video_id)

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