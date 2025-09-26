import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def resilient_consumer(max_retries=3, delay=5):
    """
    A decorator that makes a RabbitMQ consumer resilient to transient errors.
    It wraps the task processing function with a retry loop.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(channel, method, properties, body):
            retries = 0
            while retries < max_retries:
                try:
                    # Attempt to execute the original function
                    return func(channel, method, properties, body)
                except Exception as e:
                    retries += 1
                    logger.warning(f"Consumer function '{func.__name__}' failed (Attempt {retries}/{max_retries}): {e}")
                    if retries >= max_retries:
                        logger.error(f"Max retries reached for function '{func.__name__}'. The message will be acknowledged and not retried further.")
                        # Here you could add logic to move the message to a dead-letter queue
                        # For now, we just acknowledge to prevent it from being re-queued indefinitely
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        # You might want to mark the corresponding video as FAILED in the DB here
                        # This logic will be handled within the consumer function itself after the exception.
                        break 
                    
                    backoff_time = delay * (2 ** (retries - 1))
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
            # This part is reached only if all retries fail
            # The final exception handling and DB update should be in the consumer itself.
        return wrapper
    return decorator
