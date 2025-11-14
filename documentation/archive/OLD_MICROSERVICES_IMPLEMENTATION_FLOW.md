# Microservices Implementation Flow

This diagram illustrates the high-level logic and data flow of the distributed microservices system. It shows how services communicate via a command queue and an event bus to process a channel summarization job. This document reflects the final implementation after the introduction of microservices, databases, and a hybrid messaging system.

```mermaid
graph TD
    subgraph User & API
        A[User] -- POST /jobs --> B(Orchestrator API);
        A -- GET /jobs/{job_id} --> B;
        B -- Reads Job Status --> DB[(PostgreSQL)];
    end

    subgraph Command Workflow (RabbitMQ Queues)
        B -- Publishes Command --> Q1(discovery_queue);
        Q1 --> S1(Discovery Service);
        S1 -- Publishes Command --> Q2(download_queue);
        Q2 --> S2(Download Service);
        S2 -- Publishes Command --> Q3(audio_extraction_queue);
        Q3 --> S3(Audio Extraction Service);
        S3 -- Publishes Command --> Q4(transcription_queue);
        Q4 --> S4(Transcription Service);
        S4 -- Publishes Command --> Q5(summarization_queue);
        Q5 --> S5(Summarization Service);
    end

    subgraph State & Data Persistence
        S1 -- Creates/Reads Video Records --> DB;
        S2 -- Updates Video Status/Paths --> DB;
        S3 -- Updates Video Status/Paths --> DB;
        S4 -- Updates Video Status --> DB;
        S4 -- Writes Transcription --> MDB[(MongoDB)];
        S5 -- Updates Video Status --> DB;
        S5 -- Writes Summary --> MDB;
    end

    subgraph Event Streaming (Kafka Topics & RabbitMQ Fanout)
        S1 -- Publishes Event --> E1(video_discovered);
        S2 -- Publishes Event --> E2(video_downloaded);
        S3 -- Publishes Event --> E3(audio_extracted);
        S4 -- Publishes Event --> E4(transcription_completed);
        S5 -- Publishes Event --> E5(summarization_completed);
        
        E1 & E2 & E3 & E4 & E5 --> C1(Analytics Service);
        E1 & E2 & E3 & E4 & E5 --> C2(Logging Service);
        E1 & E2 & E3 & E4 & E5 --> C3(Future Consumers...);
    end

    style S1 fill:#f9f,stroke:#333,stroke-width:2px
    style S2 fill:#f9f,stroke:#333,stroke-width:2px
    style S3 fill:#f9f,stroke:#333,stroke-width:2px
    style S4 fill:#f9f,stroke:#333,stroke-width:2px
    style S5 fill:#f9f,stroke:#333,stroke-width:2px
```

### Flow Explanation

1.  **Job Submission**: A user submits a `channel_id` to the `Orchestrator API`, which generates a `job_id` and publishes a `discover` command to a **RabbitMQ** queue.
2.  **Command-Based Workflow**: Each microservice consumes a command from its designated queue, performs a single task (e.g., downloading a video), updates the video's state in the central **PostgreSQL** database, and publishes a command for the next service in the chain. This ensures each step of the pipeline is processed sequentially and reliably.
3.  **Data Storage**: Structured metadata and processing status for each video are stored in **PostgreSQL**. Large, unstructured artifacts like transcriptions and summaries are stored in **MongoDB**.
4.  **Event Streaming**: After successfully completing its task, each service publishes a domain event (e.g., `VideoDownloaded`) to a **Kafka** event bus (and a parallel RabbitMQ fanout exchange). This allows multiple, decoupled consumer services (like `Analytics Service` or `Logging Service`) to subscribe to and react to these events in real-time without impacting the core processing workflow.
5.  **Status Monitoring**: The user can poll the `Orchestrator API` with the `job_id` to get the current status of all videos in the job, which the orchestrator retrieves from the PostgreSQL database.

### Concurrency Model

The system employs a multi-layered concurrency strategy to maximize throughput and scalability:

1.  **Pipeline-Level Concurrency (Inter-Service)**:
    *   **Mechanism**: The primary driver of concurrency is the **RabbitMQ message queue**. Multiple videos from one or more jobs can be processed concurrently, as each video is a separate message in a queue.
    *   **Horizontal Scaling**: CPU-intensive services like `Transcription` and I/O-bound services like `Download` can be scaled horizontally by running multiple container instances. RabbitMQ's competing consumer pattern ensures that messages from the queue are distributed among the available worker instances, allowing the system to process many videos in parallel across the pipeline.

2.  **Event-Driven Concurrency (Decoupled Consumers)**:
    *   **Mechanism**: The **Kafka** and RabbitMQ Fanout event buses allow for a high degree of concurrency. When a service publishes an event, it is broadcast to all subscribed consumers simultaneously.
    *   **Benefit**: This allows multiple independent systems (e.g., `Analytics Service`, `Logging Service`, external notification systems) to process the same event in parallel without blocking or affecting the main processing pipeline.

3.  **Service-Level Concurrency (Intra-Service)**:
    *   **Mechanism**: Within certain services, a hybrid approach of threading and `asyncio` is used to handle I/O-bound operations efficiently.
    *   **Example (`summarization_service`)**: This service runs its Flask API server in the main thread to handle synchronous HTTP requests (like the stateless `/summarize-text` endpoint). Simultaneously, it runs the RabbitMQ worker (`pika` consumer) in a separate background thread. Within the API endpoints and the consumer logic, `asyncio.run()` is used to call the `OpenAISummarizerAgent`, which is I/O-bound due to network calls to the OpenAI API. This prevents the service from blocking while waiting for external API responses.