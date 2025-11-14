# Current System Architecture

## Overview
The YouTube Channel Summarizer has evolved from a microservices architecture to a patterns-based architecture that maintains the service separation while eliminating code duplication through the Template Method pattern and Factory pattern.

## Architectural Patterns

### 1. Service Template Pattern
The core of the system now uses the Template Method pattern implemented in `ServiceTemplatePattern.py`:

- All services inherit from `ServiceTemplate[T]` where T is the return type
- Common workflow is standardized: 
  1. Receive message from queue
  2. Update status to in-progress
  3. Execute service-specific pipeline
  4. On success: update status, send next message, publish event
  5. On failure: update status to FAILED
- Each service only implements its specific business logic in `execute_pipeline()`
- Significantly reduces code duplication (services went from ~200 to ~50 lines each)

### 2. Manager Factory Pattern
The ManagerFactory creates consistent database, queue, and event managers:

- All services use the same factory to create managers
- Ensures consistent configuration and behavior
- Reduces boilerplate code in services

### 3. Pipeline Tools Abstraction
Pipeline tools handle their own concerns:
- Each tool (AudioExtractor, VideoDownloader, etc.) handles its specific domain operation
- Tools handle their own logging when video_id is provided
- Separates business logic from service orchestration

## Component Responsibilities

### Service Layer (src/services/)
- Each service extends ServiceTemplate
- Only implements execute_pipeline() method
- Handles workflow coordination
- Updates database status
- Sends messages to next service
- Publishes events

### Pipeline Tools Layer (src/pipeline/)
- Each tool handles specific business domain functionality
- Tools manage their own internal complexity
- Automatic logging when video_id provided
- Independent of service orchestration logic

### Manager Layer (src/utils/)
- Database, queue, and event managers
- Consistent interfaces across all services
- Handles infrastructure concerns

### Pattern Layer (src/patterns/)
- ServiceTemplate: Implements Template Method pattern
- ManagerFactory: Implements Factory pattern
- Common architectural patterns

## Communication Flow
1. Message arrives via RabbitMQ
2. Service processes message using template pattern
3. Service calls its pipeline tool
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