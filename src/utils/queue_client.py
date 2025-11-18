import pika
import json
import logging
import time
from threading import Lock
from src.constants.connection_constants import DEFAULT_RABBITMQ_HOST
from src.constants.time_constants import RABBITMQ_BLOCKED_CONNECTION_TIMEOUT, RABBITMQ_SOCKET_TIMEOUT, RABBITMQ_HEARTBEAT_INTERVAL

class QueueClient:
    def __init__(self, host=DEFAULT_RABBITMQ_HOST, logger=None):
        self.host = host
        self.logger = logger or logging.getLogger(__name__)
        self.connection = None
        self.channel = None
        self.connection_lock = Lock()  # Thread-safe connection handling
        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ with retry logic."""
        while True:
            try:
                # Create connection with proper parameters for stability
                params = pika.ConnectionParameters(
                    host=self.host,
                    heartbeat=RABBITMQ_HEARTBEAT_INTERVAL,  # Enable heartbeat to detect connection loss
                    blocked_connection_timeout=RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,  # Timeout for blocked connections
                    socket_timeout=RABBITMQ_SOCKET_TIMEOUT
                )
                self.connection = pika.BlockingConnection(params)
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=1)  # Control message flow
                self.logger.info("Successfully connected to RabbitMQ.")
                break
            except pika.exceptions.AMQPConnectionError as e:
                self.logger.error(f"Could not connect to RabbitMQ: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Unexpected error connecting to RabbitMQ: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def _ensure_connection(self):
        """Ensure the RabbitMQ connection is active, reconnect if necessary."""
        with self.connection_lock:
            if not self.connection or self.connection.is_closed:
                self.logger.info("Connection closed, creating new connection...")
                self._connect()
            elif not self.channel or self.channel.is_closed:
                self.logger.info("Channel closed, creating new channel...")
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=1)

    def declare_queue(self, queue_name):
        self._ensure_connection()
        self.channel.queue_declare(queue=queue_name, durable=True)

    def publish_message(self, queue_name, message_body):
        try:
            self._ensure_connection()
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message_body),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ))
            self.logger.info(f"Sent message to queue '{queue_name}': {message_body}")
        except pika.exceptions.StreamLostError as e:
            self.logger.error(f"Stream lost error during message publishing: {e}")
            # Reconnect and try once more
            try:
                self._connect()
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=json.dumps(message_body),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    ))
                self.logger.info(f"Retried and sent message to queue '{queue_name}': {message_body}")
            except Exception as retry_error:
                self.logger.error(f"Retry also failed: {retry_error}")
        except Exception as e:
            self.logger.error(f"Failed to publish message to queue '{queue_name}': {e}")

    def start_consuming(self, queue_name, callback):
        # Ensure connection is established
        self._ensure_connection()
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)
        self.logger.info(f"Waiting for messages on queue '{queue_name}'. To exit press CTRL+C")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
        except Exception as e:
            self.logger.error(f"Error during message consumption: {e}")
        finally:
            if self.connection and self.connection.is_open:
                self.connection.close()
                self.logger.info("RabbitMQ connection closed.")

    def close_connection(self):
        with self.connection_lock:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                self.logger.info("RabbitMQ connection closed.")
