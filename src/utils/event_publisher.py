import pika
import json
import logging
import time

class EventPublisher:
    def __init__(self, host='localhost', exchange_name='events_exchange', logger=None):
        self.host = host
        self.exchange_name = exchange_name
        self.logger = logger or logging.getLogger(__name__)
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
                self.channel = self.connection.channel()
                self.channel.exchange_declare(exchange=self.exchange_name, exchange_type='fanout')
                self.logger.info(f"Successfully connected to RabbitMQ and declared exchange '{self.exchange_name}'.")
                break
            except pika.exceptions.AMQPConnectionError as e:
                self.logger.error(f"Could not connect to RabbitMQ for event publishing: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def publish(self, event_type, event_data):
        """
        Publishes an event to the fanout exchange.
        """
        message = {
            "event_type": event_type,
            "payload": event_data
        }
        try:
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
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            # In a real-world scenario, you might want to handle reconnection here.

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.logger.info("RabbitMQ event publisher connection closed.")
