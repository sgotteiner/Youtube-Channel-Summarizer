# Microservices Architecture Proposal

This document outlines a proposed microservices architecture for the YouTube Channel Summarizer. The goal is to refactor the current monolithic pipeline into a set of independently scalable, resilient, and maintainable services that communicate via a central manager and a message queue.

## 1. Identified Bottlenecks

The current pipeline has several stages with different performance characteristics:

-   **I/O-Heavy (Network/Disk)**:
    -   **Video Downloading**: High bandwidth and disk I/O. The primary bottleneck is the network connection.
    -   **API Calls (YouTube & OpenAI)**: Network latency can be a factor, but these are generally lightweight compared to file operations.
-   **CPU-Heavy (Compute)**:
    -   **Audio Transcription**: The most resource-intensive stage, requiring significant CPU power for speech-to-text processing.
    -   **Audio Extraction**: Moderately CPU-intensive, involving video file decoding.
-   **Lightweight**:
    -   **Video Discovery & Metadata Fetching**: Simple, fast API calls.

This mix of workloads is a perfect candidate for a microservices architecture, where each type of workload can be scaled independently.

## 2. Proposed Architecture Overview

The proposed architecture consists of several distinct microservices, a central API/Orchestration service, a message queue for task management, and a database for state persistence.

```mermaid
graph TD
    subgraph User Interaction
        A[User/Client] --> B{Orchestration Service API};
    end

    subgraph Core Infrastructure
        B -- "New Job: channel_url" --> C[Message Queue (e.g., RabbitMQ/Kafka)];
        B -- "Writes/Reads Job Status" --> D[Database (e.g., PostgreSQL/MongoDB)];
    end

    subgraph Worker Services
        C -- "video_discovery_queue" --> E[Discovery Service];
        E -- "Publishes video_metadata" --> C;
        E -- "Writes/Reads Video State" --> D;

        C -- "video_download_queue" --> F[Download Service];
        F -- "Publishes video_downloaded" --> C;
        F -- "Writes/Reads Video State" --> D;

        C -- "audio_extraction_queue" --> G[Audio Extraction Service];
        G -- "Publishes audio_extracted" --> C;
        G -- "Writes/Reads Video State" --> D;

        C -- "transcription_queue" --> H[Transcription Service];
        H -- "Publishes transcription_complete" --> C;
        H -- "Writes/Reads Video State" --> D;

        C -- "summarization_queue" --> I[Summarization Service];
        I -- "Publishes summary_complete" --> C;
        I -- "Writes/Reads Video State" --> D;
    end

    style E fill:#f9f,stroke:#333,stroke-width:2px
    style F fill:#f9f,stroke:#333,stroke-width:2px
    style G fill:#f9f,stroke:#333,stroke-width:2px
    style H fill:#f9f,stroke:#333,stroke-width:2px
    style I fill:#f9f,stroke:#333,stroke-width:2px
```

### 3. Components

#### 3.1. Orchestration Service (Manager)

-   **Responsibility**: Provides the public-facing API to start and monitor summarization jobs. It initiates the pipeline by placing the first task (e.g., `discover_videos`) onto the message queue. It does not perform any heavy lifting itself.
-   **API**:
    -   `POST /jobs`: Accepts a channel URL and returns a `job_id`.
    -   `GET /jobs/{job_id}`: Returns the status of a job and the summaries of completed videos.
-   **State**: This service should be **stateless**. It can be horizontally scaled. The state of each job is stored in the database.

#### 3.2. Message Queue

-   **Technology**: **RabbitMQ** or **Redis** would be excellent for task queuing. Kafka could be used but might be overkill unless you need event streaming.
-   **Purpose**: Decouples the services. The Orchestrator and worker services publish tasks (messages) to specific queues. This allows for resilience; if a service is down, the tasks remain in the queue to be processed later.
-   **Example Queues**: `discovery_queue`, `download_queue`, `transcription_queue`, `summarization_queue`.

#### 3.3. Database

-   **Technology**: A hybrid approach or a flexible NoSQL database would be ideal.
    -   **PostgreSQL (SQL)**: Excellent for storing structured data like job status, video metadata (URL, title, duration), and relationships.
    -   **MongoDB (NoSQL)**: A great choice for storing unstructured data like transcriptions and summaries. Its flexible schema is advantageous here.
-   **Purpose**: Acts as the single source of truth for the state of the system. It stores:
    -   Job information (which channel, status, creation time).
    -   Video metadata and the processing status of each video (e.g., `PENDING`, `DOWNLOADING`, `TRANSCRIBING`, `COMPLETE`).
    -   Paths to stored artifacts (video, audio files) if they are kept.
    -   The final transcriptions and summaries.

#### 3.4. Worker Microservices

Each worker service is a small, independent application that performs one specific task. They listen to a queue, process a message, and publish a new message to the next queue or update the database. All worker services should be **stateless** and horizontally scalable.

1.  **Discovery Service**:
    -   **Listens to**: `discovery_queue`.
    -   **Task**: Receives a channel URL. Fetches the list of videos, filters out already processed ones (by checking the DB), and publishes a message for each new video to the `download_queue`.
    -   **Scalability**: Lightweight, likely needs only one or two instances.

2.  **Download Service**:
    -   **Listens to**: `download_queue`.
    -   **Task**: Receives video metadata. Downloads the video file to a shared storage location (like an S3 bucket or a network file system). Updates the video's status to `DOWNLOADED` in the DB and publishes a message to the `audio_extraction_queue`.
    -   **Scalability**: I/O-bound. Can be scaled out to increase download throughput.

3.  **Audio Extraction Service**:
    -   **Listens to**: `audio_extraction_queue`.
    -   **Task**: Receives the path to a downloaded video. Extracts the audio and saves it to shared storage. Updates the DB and publishes to the `transcription_queue`.
    -   **Scalability**: CPU-bound. Scale this service based on CPU load.

4.  **Transcription Service**:
    -   **Listens to**: `transcription_queue`.
    -   **Task**: Receives the path to an audio file. Performs speech-to-text. Saves the transcription to the database. Updates the video's status to `TRANSCRIBED` and publishes to the `summarization_queue`.
    -   **Scalability**: **Very CPU-heavy**. This service will require the most aggressive scaling. You can run many instances of it on powerful machines.

5.  **Summarization Service**:
    -   **Listens to**: `summarization_queue`.
    -   **Task**: Receives a transcription. Calls the OpenAI API to get a summary. Saves the summary to the database and marks the video as `COMPLETE`.
    -   **Scalability**: I/O-bound (API calls). Can be scaled out to handle many concurrent API requests.

## 4. State Management and Communication

-   **Stateless vs. Stateful**: All worker services are **stateless**. They receive all the information they need in the task message (e.g., `video_id`). The state of the workflow is persisted in the **Database**. The Orchestration service is also stateless. This is key to allowing horizontal scaling.
-   **Communication**: Asynchronous communication via the **Message Queue** is preferred over direct service-to-service (HTTP) calls. This makes the system more resilient to individual service failures. The Orchestrator can use the database to track the progress of a video through the pipeline.
