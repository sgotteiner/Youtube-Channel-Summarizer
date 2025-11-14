"""
Async worker for RabbitMQ consumption that bridges threading and asyncio.
"""
import asyncio
import json
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any
from src.utils.logger import setup_logging
from src.utils.queue_client import QueueClient


class AsyncWorker(ABC):
    """
    An async worker that consumes from RabbitMQ queues and processes messages
    using asyncio coroutines, while handling the threading complexity internally.
    """
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.logger = setup_logging()
        self.loop = None
        self.queue_client = None
        self._running = False
        self._tasks = set()

    async def initialize(self):
        """Initialize the worker components."""
        self.queue_client = QueueClient(logger=self.logger)
        self.queue_client.declare_queue(self.queue_name)
        self.loop = asyncio.get_event_loop()

    def run(self):
        """Run the worker synchronously (starts the consumer thread)."""
        asyncio.run(self._run_async())

    async def _run_async(self):
        """Run the worker asynchronously."""
        await self.initialize()
        self.logger.info(f"Starting AsyncWorker for queue '{self.queue_name}'")
        
        # Start the RabbitMQ consumer thread
        consumer_thread = threading.Thread(target=self._start_consumer, daemon=True)
        consumer_thread.start()
        
        try:
            self._running = True
            # Keep the main thread alive to handle async tasks
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down worker...")
        finally:
            await self._cleanup()

    def _start_consumer(self):
        """Start the RabbitMQ consumer in a separate thread."""
        self.queue_client.start_consuming(self.queue_name, self._process_message_sync)

    def _process_message_sync(self, channel, method, properties, body):
        """
        Synchronous callback from RabbitMQ that schedules async processing.
        """
        # Acknowledge immediately to avoid delivery tag conflicts
        try:
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            self.logger.error(f"Error acknowledging message: {e}")
            return

        # Schedule the async processing in the event loop
        data = json.loads(body)
        task = asyncio.run_coroutine_threadsafe(
            self._process_message_async(data), self.loop
        )
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    async def _process_message_async(self, data: Dict[str, Any]):
        """
        Process the message asynchronously. This method should be overridden
        by subclasses to implement specific message handling.
        """
        try:
            success = await self.process_message(data)
            if not success:
                self.logger.error(f"Message processing failed for data: {data}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    @abstractmethod
    async def process_message(self, data: Dict[str, Any]) -> bool:
        """
        Process a message asynchronously. Must be implemented by subclasses.
        Return True if processing was successful, False otherwise.
        """
        pass

    def _on_task_done(self, task):
        """Callback when an async task completes."""
        self._tasks.discard(task)
        if task.exception():
            self.logger.error(f"Async task failed: {task.exception()}")

    async def _cleanup(self):
        """Clean up resources."""
        self._running = False
        # Cancel all pending tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        if self.queue_client:
            self.queue_client.close_connection()