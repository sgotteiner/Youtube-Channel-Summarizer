import pika
import json
import logging
import time

class QueueClient:
    def __init__(self, host='rabbitmq', logger=None):
        self.host = host
        self.logger = logger or logging.getLogger(__name__)
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
                self.channel = self.connection.channel()
                self.logger.info("Successfully connected to RabbitMQ.")
                break
            except pika.exceptions.AMQPConnectionError as e:
                self.logger.error(f"Could not connect to RabbitMQ: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def declare_queue(self, queue_name):
        self.channel.queue_declare(queue=queue_name, durable=True)

    def publish_message(self, queue_name, message_body):
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message_body),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        self.logger.info(f"Sent message to queue '{queue_name}': {message_body}")

    def start_consuming(self, queue_name, callback):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)
        self.logger.info(f"Waiting for messages on queue '{queue_name}'. To exit press CTRL+C")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.connection.close()
            self.logger.info("RabbitMQ connection closed.")

    def close_connection(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.logger.info("RabbitMQ connection closed.")
