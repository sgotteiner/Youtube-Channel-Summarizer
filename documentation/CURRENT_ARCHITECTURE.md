# Current System Architecture

## Overview
The YouTube Channel Summarizer has been transformed from a monolithic application to a microservices architecture with design patterns. The primary focus of the recent refactoring was to eliminate code duplication and standardize the service interfaces.

## Architectural Patterns

### 1. Service Template Pattern
The core of the system now uses the Template Method pattern implemented in `ServiceTemplatePattern.py`:

- All services inherit from `ServiceTemplate[T]` where T is the return type
- Common workflow is standardized:
  1. Receive message from queue
  2. Update status to in-progress
  3. Execute service-specific pipeline via `execute_pipeline` method
  4. On success: update status, send next message, publish event
  5. On failure: update status to FAILED
- Each service only implements its specific business logic in `execute_pipeline()`
- Eliminates code duplication significantly (services went from ~200 to ~50 lines each)

### 2. Factory Pattern
The ManagerFactory creates consistent database, queue, and event managers:

- All services use the same factory to create managers
- Ensures consistent configuration and behavior
- Reduces boilerplate code in services

### 3. Pipeline Tools Abstraction
Pipeline tools handle their specific domain operations:
- Each tool (AudioExtractor, VideoDownloader, etc.) handles its specific domain operation
- Tools handle their own file path logic using the FileManager
- Separates business logic from service orchestration

## Component Responsibilities

### Service Layer (src/services/)
- Each service extends ServiceTemplate
- Only implements execute_pipeline() method and helper methods
- Handles workflow coordination
- Updates database status
- Sends messages to next service
- Publishes events

### Pipeline Tools Layer (src/pipeline/)
- Each tool handles specific business domain functionality
- Tools manage their own internal complexity
- Automatic logging when video_id provided
- Uses FileManager for path operations
- Separates business logic from service orchestration

### Manager Layer (src/utils/)
- Database, queue, and event managers
- Consistent interfaces across all services
- Handles infrastructure concerns

### Pattern Layer (src/patterns/)
- ServiceTemplate: Implements Template Method pattern
- ManagerFactory: Implements Factory pattern
- Common architectural patterns

## Service Orchestration Pattern
The ServiceTemplate handles the common orchestration pattern:
- Setup file paths using FileManager with video metadata
- Validate input file paths when needed using consistent validation
- Call service-specific operations implemented in each service
- Handle success/failure with standard database updates, messaging, and events

## Communication Flow
1. Message arrives via RabbitMQ
2. Service processes message using template pattern
3. Service calls its pipeline tool with proper paths from FileManager
4. Pipeline tool performs operation and logs automatically
5. Success: Service updates DB, sends next message, publishes event
6. Failure: Service updates DB to FAILED status

## Benefits of Current Architecture
- Minimal code duplication through patterns
- Consistent behavior across all services
- Easy to add new services using same template
- Clear separation of concerns
- Maintains scalability of microservices approach
- Cleaner code following Single Responsibility Principle
- Services focus on orchestration, pipeline tools handle domain logic
- File path consistency through centralized FileManager
- Proper error handling and logging patterns