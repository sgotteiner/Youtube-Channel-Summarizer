# Application Concurrency Flow

This diagram illustrates how the application handles concurrent operations. It shows the relationship between the main `asyncio` event loop (which runs on the Main Thread) and the `ThreadPoolExecutor` (which manages a pool of Worker Threads for blocking tasks).

```mermaid
graph TD
    subgraph Main Thread
        A[Start: asyncio.run(main)] --> B[Create ThreadPoolExecutor];
        B --> C[asyncio.gather starts N tasks];
        C --> D1[process_video_wrapper 1];
        C --> D2[process_video_wrapper 2];
        C --> D3[...];
    end

    subgraph "process_video_wrapper (Coroutine)"
        D1 --> E{I/O or CPU-bound task?};
        E -- "No (Native Await)" --> F[Async Operation e.g., await AgentSummarizer];
        F --> G[Event Loop runs other tasks];
        G --> H[Async Operation Completes];
        H --> E;

        E -- "Yes (Blocking Code)" --> I[loop.run_in_executor(...)];
    end

    subgraph "ThreadPoolExecutor (Worker Threads)"
        I -- Delegates task --> J[Worker Thread];
        J --> K[Execute Blocking Function e.g., audio_transcriber.transcribe_audio];
        K --> L[Task Completes];
        L -- Returns result --> M[Awaitable in Coroutine];
    end

    M --> H;

    subgraph Legend
        direction LR
        LEG1(Async Coroutine) -- Manages --> LEG2(Blocking Function);
        LEG2 -- Runs inside --> LEG3(Worker Thread);
        LEG1 -- Runs on --> LEG4(Main Thread / Event Loop);
    end

    style D1 fill:#f9f,stroke:#333,stroke-width:2px
    style D2 fill:#f9f,stroke:#333,stroke-width:2px
    style D3 fill:#f9f,stroke:#333,stroke-width:2px
```

### **Breakdown of Operations:**

*   **Native `async` Operations (Run on Main Thread):**
    *   `AgentSummarizer.summary_call`: The call to the OpenAI API uses an `async` library (`AsyncOpenAI`) and is awaited directly in the event loop.
    *   `aiofiles`: All file writing (`.txt` summaries and transcriptions) is handled asynchronously on the main thread.

*   **Blocking Operations (Delegated to `ThreadPoolExecutor`):**
    *   `VideoMetadataFetcher.get_video_entries` & `fetch_video_details`: All calls to `yt-dlp` for metadata are synchronous and are run in the executor.
    *   `VideoDownloader.download_video` & `download_captions`: All video and caption downloads (`pytubefix`, `yt-dlp`) are run in the executor.
    *   `AudioExtractor.extract_audio`: Audio extraction (`moviepy`) is CPU-bound and is run in the executor.
    *   `AudioTranscriber.transcribe_audio`: The entire audio transcription process (`pydub`, `SpeechRecognition`) is CPU-bound and is run in the executor.
    *   `FileManager.cleanup_intermediate_files`: File deletion is run in the executor to avoid blocking.
