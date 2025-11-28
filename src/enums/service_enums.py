from enum import Enum


class ServiceType(Enum):
    """Enumeration for service types using numerical indexes."""
    DISCOVERY = 0
    DOWNLOAD = 1
    TRANSCRIPTION = 2
    SUMMARIZATION = 3

class ProcessingStatus(Enum):
    """Enum representing the processing status of a video."""
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"