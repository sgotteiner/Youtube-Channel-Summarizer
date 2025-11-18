# Current Software Design Patterns

## Overview
The YouTube Channel Summarizer implements several key design patterns that enable clean, maintainable code while supporting the microservices architecture.

## Primary Patterns

### Template Method Pattern
Implemented in `ServiceTemplate[T]` in `src/patterns/ServiceTemplatePattern.py`:

**Purpose**: Standardize the common workflow across all services while allowing customization of specific operations.

**Implementation**:
- Abstract base class `ServiceTemplate[T]` with generic type parameter
- Template method `process_message()` implements the common workflow:
  - Retrieve video from database
  - Call service-specific `execute_pipeline()` method
  - Handle success/failure with standard operations
- Concrete services only implement the `execute_pipeline()` method
- Provides helper methods: `create_file_manager()`, `prepare_video_data()`, `validate_input_file_path()`

**Benefits**:
- Eliminates code duplication (~200 lines per service → ~50 lines per service)
- Ensures consistent behavior across all services
- Maintains flexibility for service-specific logic
- Enables easy addition of new services

### Factory Pattern
Implemented in `ManagerFactory` in `src/patterns/manager_factory.py`:

**Purpose**: Create consistent database, queue, and event manager instances.

**Implementation**:
- Static methods for creating all required managers
- Consistent configuration and behavior across all services
- Centralized management of dependencies

**Benefits**:
- Ensures consistent manager behavior
- Reduces boilerplate code in services
- Simplifies testing with mock managers

### Strategy Pattern Elements
Used internally in ServiceTemplate for different service types:

**Implementation**:
- ServiceTemplate uses service-specific mappings based on service_type
- Each service gets appropriate status, queue, and event names automatically
- Standardized handling with service-specific adjustments

## Helper Methods Pattern
The ServiceTemplate provides standardized helper methods:

### create_file_manager(video)
- Creates standardized FileManager instance with consistent parameters
- Uses video.channel_name and default settings
- Ensures consistent file path generation across services

### prepare_video_data(video, video_id)
- Prepares standardized video data dictionary
- Ensures consistent video metadata format for file operations
- Maps video attributes to required fields

### validate_input_file_path(file_path, video_id)
- Validates that specified file paths exist
- Provides consistent error logging
- Returns None if path doesn't exist

## Service Architecture Pattern
Each service follows a standardized implementation pattern:

### Standard Service Structure
```
class XxxService(ServiceTemplate[T]):
    def __init__(self):
        super().__init__("service_type")
        self.pipeline_tool = XxxPipelineTool(self.logger)

    async def execute_pipeline(self, video, video_id: str) -> T:
        # 1. Get file paths using helper methods
        file_manager = self.create_file_manager(video)
        video_data = self.prepare_video_data(video, video_id)
        video_paths = file_manager.get_video_paths(video_data)

        # 2. Validate input if needed
        input_path = self.validate_input_file_path(video_paths["input"], video_id)
        if not input_path:
            return None

        # 3. Call pipeline tool with paths from FileManager
        result = await self.pipeline_tool.specific_operation(
            input_path, video_paths["output"], video_id
        )

        return result

    def get_service_specific_event_fields(self, video_id: str, video, result: T) -> dict:
        # Return service-specific fields for event payload
        return {...}
```

### Benefits of Standardized Pattern
- Consistent structure across all services
- Clear separation of concerns (Service: orchestration, Pipeline Tool: business logic)
- Easy to understand and maintain
- Reduced cognitive load for developers

## Pipeline Tool Interface Pattern
Pipeline tools follow a consistent interface pattern:

### Standard Pipeline Tool Structure
```
class XxxPipelineTool:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def specific_operation(self, input_path: Path, output_path: Path, video_id: str = None) -> Optional[Path]:
        # Operation logic with automatic logging
        # Input validation
        # Processing
        # Output handling
        pass
```

## FileManager Integration Pattern
All file operations use centralized FileManager:

**Implementation**:
- Service gets paths via `file_manager.get_video_paths(video_data)`
- Consistent file naming and directory structure
- Shared file path logic across services
- Consistent sanitization (replaces spaces with underscores)

**Benefits**:
- No duplicate file path logic
- Consistent file naming across services
- Easy to modify file structure in one place
- Prevents file path mismatches between services

## Error Handling Pattern
Consistent error handling across all services:

### In ServiceTemplate:
- Standardized try-catch blocks in `process_message`
- Consistent status updates for success/failure
- Centralized logging patterns

### In Pipeline Tools:
- Input validation with consistent error messages
- Proper exception handling with meaningful logs
- Automatic status logging with video_id

## Event Payload Pattern
Services build event payloads using a consistent approach:
- Base payload with common fields (video_id, job_id, completed_at)
- Service-specific fields added via `get_service_specific_event_fields`
- Automatic inclusion of additional fields like character counts, file paths, etc.

This design ensures all components work together harmoniously while maintaining the separation of concerns necessary for a scalable microservices architecture.