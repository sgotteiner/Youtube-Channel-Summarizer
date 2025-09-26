import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError
import time

class KafkaEventProducer:
    def __init__(self, bootstrap_servers='kafka:29092', logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.producer = None
        while self.producer is None:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    retries=5,
                    acks='all'
                )
                self.logger.info("Successfully connected to Kafka.")
            except KafkaError as e:
                self.logger.error(f"Failed to connect to Kafka: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def send_event(self, topic, event_data):
        try:
            future = self.producer.send(topic, event_data)
            # Block for 'successful' sends
            record_metadata = future.get(timeout=10)
            self.logger.info(f"Event sent to Kafka topic '{record_metadata.topic}'.")
            return record_metadata
        except KafkaError as e:
            self.logger.error(f"Error sending event to Kafka: {e}")
            return None

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
            self.logger.info("Kafka producer connection closed.")
