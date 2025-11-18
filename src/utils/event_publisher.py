import pika
import json
import logging
import time
from threading import Lock
from src.constants.service_constants import EVENTS_EXCHANGE_NAME
from src.constants.time_constants import (RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,
                                         RABBITMQ_SOCKET_TIMEOUT)

class EventPublisher:
    def __init__(self, host='rabbitmq', exchange_name=EVENTS_EXCHANGE_NAME, logger=None):
        self.host = host
        self.exchange_name = exchange_name
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
                    heartbeat=600,  # Enable heartbeat to detect connection loss
                    blocked_connection_timeout=RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,  # Timeout for blocked connections
                    socket_timeout=RABBITMQ_SOCKET_TIMEOUT
                )
                self.connection = pika.BlockingConnection(params)
                self.channel = self.connection.channel()
                self.channel.exchange_declare(exchange=self.exchange_name, exchange_type='fanout')
                self.logger.info(f"Successfully connected to RabbitMQ and declared exchange '{self.exchange_name}'.")
                break
            except pika.exceptions.AMQPConnectionError as e:
                self.logger.error(f"Could not connect to RabbitMQ for event publishing: {e}. Retrying in 5 seconds...")
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
                self.channel.exchange_declare(exchange=self.exchange_name, exchange_type='fanout')

    def publish(self, event_type, event_data):
        """
        Publishes an event to the fanout exchange.
        """
        message = {
            "event_type": event_type,
            "payload": event_data
        }
        
        try:
            self._ensure_connection()
            
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key='',  # routing_key is ignored for fanout exchanges
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    delivery_mode=2,  # make message persistent
                )
            )
            self.logger.info(f"Published event '{event_type}' to exchange '{self.exchange_name}'.")
        except pika.exceptions.StreamLostError as e:
            self.logger.error(f"Stream lost error during event publishing: {e}")
            # Reconnect and try once more
            try:
                self._connect()
                self.channel.basic_publish(
                    exchange=self.exchange_name,
                    routing_key='',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        content_type='application/json',
                        delivery_mode=2,
                    )
                )
                self.logger.info(f"Retried and published event '{event_type}' to exchange '{self.exchange_name}'.")
            except Exception as retry_error:
                self.logger.error(f"Retry also failed: {retry_error}")
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")

    def close(self):
        with self.connection_lock:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                self.logger.info("RabbitMQ event publisher connection closed.")
