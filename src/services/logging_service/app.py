"""
Logging Service - Consumes events from the event exchange and logs them.
"""
import json
from src.utils.logger import setup_logging
from src.constants.service_constants import EVENTS_EXCHANGE_NAME
from src.constants.connection_constants import DEFAULT_RABBITMQ_HOST


class LoggingService:
    def __init__(self):
        self.logger = setup_logging()
        self.host = DEFAULT_RABBITMQ_HOST
        self.exchange_name = EVENTS_EXCHANGE_NAME
        self.queue_name = 'logging_service'

    def event_callback(self, channel, method, properties, body):
        """
        Callback function to process received events.
        """
        try:
            message = json.loads(body)
            event_type = message.get("event_type", "UnknownEvent")
            payload = message.get("payload", {})

            self.logger.info("EVENT RECEIVED [%s]: %s", event_type, json.dumps(payload))

        except json.JSONDecodeError:
            self.logger.error("Failed to decode event message: %s", body)
        except Exception as e:
            self.logger.error("An error occurred processing event: %s", e)
        finally:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    def run(self):
        """
        Main function to set up and start the event consumer.
        """
        import pika
        import time
        
        while True:
            try:
                connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
                channel = connection.channel()

                # Declare the fanout exchange (should match the publisher)
                channel.exchange_declare(exchange=self.exchange_name, exchange_type='fanout')

                # Declare an exclusive queue for this consumer. When the consumer disconnects, the queue is deleted.
                channel.queue_declare(queue=self.queue_name, durable=True)

                # Bind the queue to the exchange
                channel.queue_bind(exchange=self.exchange_name, queue=self.queue_name)

                self.logger.info("Logging service is waiting for events. To exit press CTRL+C")

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=self.queue_name, on_message_callback=self.event_callback)
                channel.start_consuming()

            except pika.exceptions.AMQPConnectionError as e:
                self.logger.error("Connection to RabbitMQ failed: %s. Retrying in 5 seconds...", e)
                time.sleep(5)
            except KeyboardInterrupt:
                self.logger.info("Shutting down logging service.")
                break
            except Exception as e:
                self.logger.error("An unexpected error occurred: %s. Restarting consumer...", e)
                time.sleep(5)


if __name__ == "__main__":
    service = LoggingService()
    service.run()