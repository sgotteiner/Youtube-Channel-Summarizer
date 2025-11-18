"""
Analytics Service - Consumes events from Kafka topics and processes them for analytics.
"""
import json
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import time
from src.utils.logger import setup_logging
from src.constants.connection_constants import DEFAULT_KAFKA_BOOTSTRAP_SERVERS


class AnalyticsService:
    def __init__(self):
        self.logger = setup_logging()
        self.topics = [
            'video_discovered',
            'video_downloaded', 
            'audio_extracted',
            'transcription_completed',
            'summarization_completed'
        ]
        self.consumer = None

    def run(self):
        """
        Main function to set up and start the Kafka consumer.
        """
        while self.consumer is None:
            try:
                self.consumer = KafkaConsumer(
                    *self.topics,
                    bootstrap_servers=DEFAULT_KAFKA_BOOTSTRAP_SERVERS,
                    auto_offset_reset='earliest',
                    enable_auto_commit=True,
                    group_id='analytics-group',
                    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
                )
                self.logger.info(f"Analytics service connected to Kafka and subscribed to topics: {self.topics}")
            except KafkaError as e:
                self.logger.error(f"Failed to connect Kafka consumer: {e}. Retrying in 5 seconds...")
                time.sleep(5)

        try:
            for message in self.consumer:
                self.logger.info(f"ANALYTICS EVENT [{message.topic}]: "
                                f"Partition={message.partition}, Offset={message.offset}, "
                                f"Key={message.key}, Value={message.value}")
        except KeyboardInterrupt:
            self.logger.info("Shutting down analytics service.")
        finally:
            if self.consumer:
                self.consumer.close()


if __name__ == "__main__":
    service = AnalyticsService()
    service.run()