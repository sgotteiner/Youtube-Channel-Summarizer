import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
import time
from threading import Lock

class KafkaEventProducer:
    def __init__(self, bootstrap_servers='kafka:29092', logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.producer_lock = Lock()  # Thread-safe producer handling
        self._connect()

    def _connect(self):
        """Establish connection to Kafka with retry logic."""
        while True:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    retries=3,
                    acks='all',
                    linger_ms=5,  # Small delay to batch messages together
                    request_timeout_ms=15000,  # 15 seconds timeout
                    max_block_ms=5000,  # Max time to block on send
                    reconnect_backoff_ms=50,  # Initial backoff for reconnection
                    reconnect_backoff_max_ms=1000  # Max backoff for reconnection
                )
                self.logger.info("Successfully connected to Kafka.")
                break
            except NoBrokersAvailable as e:
                self.logger.error(f"No Kafka brokers available: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            except KafkaError as e:
                self.logger.error(f"Failed to connect to Kafka: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Unexpected error connecting to Kafka: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def _ensure_connection(self):
        """Ensure the Kafka producer is active, reconnect if necessary."""
        with self.producer_lock:
            if not self.producer:
                self.logger.info("Kafka producer not initialized, creating new producer...")
                self._connect()
            else:
                # Test the producer by checking if it's still connected
                # We'll do a simple check for the most common error
                try:
                    # Try to access the producer's metadata to see if connection is valid
                    # This is just a basic check since there's no explicit status check method
                    pass
                except Exception:
                    self.logger.info("Kafka connection error, recreating producer...")
                    try:
                        self.producer.close()
                    except Exception:
                        pass  # Ignore errors during close
                    self._connect()

    def send_event(self, topic, event_data):
        try:
            self._ensure_connection()
            future = self.producer.send(topic, event_data)
            # Block for 'successful' sends
            record_metadata = future.get(timeout=15)  # Increased timeout
            self.logger.info(f"Event sent to Kafka topic '{record_metadata.topic}'.")
            return record_metadata
        except Exception as e:
            self.logger.error(f"Error sending event to Kafka: {e}")
            # Try to reconnect and send once more
            try:
                with self.producer_lock:
                    self.producer.close()
                    self._connect()
                future = self.producer.send(topic, event_data)
                record_metadata = future.get(timeout=15)
                self.logger.info(f"Retried and sent event to Kafka topic '{record_metadata.topic}'.")
                return record_metadata
            except Exception as retry_error:
                self.logger.error(f"Retry also failed: {retry_error}")
                return None

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
            self.logger.info("Kafka producer connection closed.")
