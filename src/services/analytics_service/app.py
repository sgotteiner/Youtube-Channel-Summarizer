import json
import logging
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import time

from src.utils.logger import setup_logging

logger = setup_logging()

def main():
    topics = [
        'video_discovered',
        'video_downloaded',
        'audio_extracted',
        'transcription_completed',
        'summarization_completed'
    ]
    
    consumer = None
    while consumer is None:
        try:
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers='kafka:29092',
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='analytics-group',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logger.info(f"Analytics service connected to Kafka and subscribed to topics: {topics}")
        except KafkaError as e:
            logger.error(f"Failed to connect Kafka consumer: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    try:
        for message in consumer:
            logger.info(f"ANALYTICS EVENT [{message.topic}]: Partition={message.partition}, Offset={message.offset}, Key={message.key}, Value={message.value}")
    except KeyboardInterrupt:
        logger.info("Shutting down analytics service.")
    finally:
        if consumer:
            consumer.close()

if __name__ == "__main__":
    main()
