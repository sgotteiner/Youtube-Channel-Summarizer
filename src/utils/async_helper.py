"""
Utility module for async helper patterns to reduce code duplication across services.
"""
import asyncio
import logging
from typing import Awaitable
import threading
from src.constants.time_constants import ASYNC_HELPER_TIMEOUT

logger = logging.getLogger(__name__)

class ServiceAsyncProcessor:
    """
    Generic async processor for service tasks to handle I/O-bound operations efficiently.
    Designed to work with a persistent event loop running in the main thread.
    """
    def __init__(self):
        self.internal_tasks = set()
        self.loop = None
        self.loop_set = threading.Event()  # Event to signal when loop is set

    def set_loop(self, loop):
        """
        Set the main event loop that will run all async tasks.
        """
        self.loop = loop
        self.loop_set.set()  # Signal that the loop is now available

    def schedule_task_with_immediate_ack(self, coroutine_func: Awaitable, channel, method):
        """
        Schedule a task and acknowledge the message immediately in the original thread.
        This avoids delivery tag conflicts between async tasks and the RabbitMQ consumer.
        """
        # Acknowledge the message immediately in the original RabbitMQ consumer thread
        try:
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            # If we can't acknowledge, try to reject instead
            try:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception:
                # If both fail, we can't do much else
                pass
        
        # Wait for the loop to be set if it's not ready yet
        self.loop_set.wait(timeout=ASYNC_HELPER_TIMEOUT)  # Wait up to 5 seconds for the loop to be set
        
        # Schedule the task in the main event loop using run_coroutine_threadsafe since
        # this is called from a different thread than the event loop
        if self.loop and not self.loop.is_closed():
            task = asyncio.run_coroutine_threadsafe(coroutine_func, self.loop)
            self.internal_tasks.add(task)
            # Add a callback to remove the task when done
            task.add_done_callback(self._on_task_complete)
            return task
        else:
            logger.error("No event loop available for scheduling task after timeout")
            # If no loop, run the coroutine synchronously as a fallback
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coroutine_func)
                # Create a simple task-like object to track the future
                task = type('FutureTask', (), {
                    'done': lambda: future.done(),
                    'result': future.result,
                    'exception': future.exception
                })()
                self.internal_tasks.add(task)
                return task

    def schedule_task(self, coroutine_func: Awaitable):
        """
        Schedule a task for async execution in the main event loop.
        """
        # Wait for the loop to be set if it's not ready yet
        self.loop_set.wait(timeout=ASYNC_HELPER_TIMEOUT)  # Wait up to 5 seconds for the loop to be set
        
        if self.loop and not self.loop.is_closed():
            task = asyncio.run_coroutine_threadsafe(coroutine_func, self.loop)
            self.internal_tasks.add(task)
            # Add a callback to remove the task when done
            task.add_done_callback(self._on_task_complete)
            return task
        else:
            logger.error("No event loop available for scheduling task after timeout")
            # If no loop, run the coroutine synchronously as a fallback
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coroutine_func)
                # Create a simple task-like object to track the future
                task = type('FutureTask', (), {
                    'done': lambda: future.done(),
                    'result': future.result,
                    'exception': future.exception
                })()
                self.internal_tasks.add(task)
                return task

    def _on_task_complete(self, task):
        """
        Callback to remove completed tasks from the internal tasks set.
        """
        self.internal_tasks.discard(task)
        if task.exception():
            logger.error(f"Async task completed with exception: {task.exception()}")

    def get_internal_task_count(self):
        """
        Get the number of internal tasks currently running.
        """
        # Remove completed tasks from the set
        completed_tasks = {t for t in self.internal_tasks if t.done()}
        self.internal_tasks -= completed_tasks
        return len(self.internal_tasks)

    def shutdown(self):
        """
        Cancel all running tasks for clean shutdown.
        """
        for task in self.internal_tasks:
            if not task.done():
                if hasattr(task, 'cancel'):
                    task.cancel()