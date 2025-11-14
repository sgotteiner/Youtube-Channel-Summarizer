"""
Factory patterns for creating service managers consistently.
"""
from src.utils.db_manager import DatabaseManager
from src.utils.queue_manager import QueueManager
from src.utils.event_manager import EventManager


class ManagerFactory:
    """
    Factory for creating managers consistently.
    Implements the Factory pattern for service managers.
    """
    @staticmethod
    def create_database_manager(logger):
        return DatabaseManager(logger)
    
    @staticmethod
    def create_queue_manager(logger):
        return QueueManager(logger)
    
    @staticmethod
    def create_event_manager(logger):
        return EventManager(logger)