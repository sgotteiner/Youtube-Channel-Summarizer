import pika
import json
import logging
import time
from src.utils.logger import setup_logging

logger = setup_logging()

def event_callback(channel, method, properties, body):
    """
    Callback function to process received events.
    """
    try:
        message = json.loads(body)
        event_type = message.get("event_type", "UnknownEvent")
        payload = message.get("payload", {})
        
        logger.info(f"EVENT RECEIVED [{event_type}]: {json.dumps(payload)}")
        
    except json.JSONDecodeError:
        logger.error(f"Failed to decode event message: {body}")
    except Exception as e:
        logger.error(f"An error occurred processing event: {e}")
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    """
    Main function to set up and start the event consumer.
    """
    host = 'localhost'
    exchange_name = 'events_exchange'
    queue_name = 'logging_service_queue'
    
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
            channel = connection.channel()

            # Declare the fanout exchange (should match the publisher)
            channel.exchange_declare(exchange=exchange_name, exchange_type='fanout')

            # Declare an exclusive queue for this consumer. When the consumer disconnects, the queue is deleted.
            result = channel.queue_declare(queue=queue_name, durable=True)
            
            # Bind the queue to the exchange
            channel.queue_bind(exchange=exchange_name, queue=queue_name)

            logger.info(f"Logging service is waiting for events. To exit press CTRL+C")
            
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=event_callback)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Connection to RabbitMQ failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Shutting down logging service.")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}. Restarting consumer...")
            time.sleep(5)

if __name__ == "__main__":
    main()
