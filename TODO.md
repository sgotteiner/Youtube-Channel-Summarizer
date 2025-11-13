# Development Todo List

## High Priority Items

### 1. Async Architecture Optimization
- **Current Issue**: Each service task runs with its own event loop using asyncio.run(), which is inefficient
- **Optimal Design**: One persistent event loop per service container managing concurrent video tasks
- **Benefits**: Better resource usage, true async concurrency, optimal I/O handling
- **Approach**: Integrate RabbitMQ with main event loop using asyncio.run_coroutine_threadsafe()

### 2. Parallel Chunk Processing Enhancement
- **Transcription Service**: Implement concurrent processing of audio chunks within a single video's transcription to speed up large audio files
- **Summarization Service**: Implement concurrent processing of text chunks for large transcriptions
- **Benefits**: Significant performance improvement for large files, better resource utilization
- **Approach**: Use asyncio.gather() or similar patterns to handle multiple chunks concurrently

## Other Items

### 3. Performance Optimizations
- Consider implementing connection pooling for database queries
- Optimize file I/O operations for better throughput
- Monitor resource usage and optimize accordingly

### 4. Observability Enhancements
- Add more detailed metrics for performance monitoring
- Improve logging around concurrent operations
- Add tracing for cross-service operations