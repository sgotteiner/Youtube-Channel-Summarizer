"""
Common service infrastructure combining all abstractions.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from src.utils.async_worker import AsyncWorker
from src.utils.service_logger import ServiceLogger


class BaseService(AsyncWorker, ABC):
    """
    Base class combining all service abstractions for easy implementation.
    """
    def __init__(self, queue_name: str):
        super().__init__(queue_name)
        from src.patterns.manager_factory import ManagerFactory
        manager_factory = ManagerFactory()
        self.db_manager = manager_factory.create_database_manager(self.logger)
        self.queue_manager = manager_factory.create_queue_manager(self.logger)
        self.event_manager = manager_factory.create_event_manager(self.logger)
        self.service_logger = ServiceLogger(self.logger)

    async def initialize(self):
        """Initialize the base service components."""
        await super().initialize()

    async def cleanup(self):
        """Clean up all service resources."""
        await super()._cleanup()
        self.queue_manager.close()
        self.event_manager.close()

    @abstractmethod
    async def process_message(self, data: Dict[str, Any]) -> bool:
        """
        Process a message asynchronously. Must be implemented by subclasses.
        Return True if processing was successful, False otherwise.
        """
        pass