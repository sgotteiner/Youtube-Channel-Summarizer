## **Architecture Design: YouTube Channel Summarizer**

**Version:** 1.0
**Date:** September 10, 2025

### **1. Introduction**

#### **1.1. Purpose**
This document provides a high-level design for the YouTube Channel Summarizer application. It covers the system architecture, components, and data flow.

#### **1.2. Scope**
The application is designed to automate the process of fetching videos from a specified YouTube channel, transcribing their audio content, and generating concise summaries using the OpenAI API. It is a command-line application intended to be run as a script.

#### **1.3. System Overview**
The YouTube Channel Summarizer is a Python application that operates as a pipeline. It identifies new videos on a channel, processes them to get a text transcription (either by downloading existing captions or by performing speech-to-text on the audio), and then uses an AI agent to summarize the transcription. The system is designed to be resilient, efficient, and configurable, with a focus on minimizing redundant work and managing costs.

---

### **2. System Architecture**

#### **2.1. Architectural Style**
The system employs a **modular, pipeline-driven architecture**. Each distinct responsibility (e.g., downloading, transcribing, summarizing) is encapsulated within its own class. A central orchestrator (`main.py`) initializes these components and manages the overall workflow, passing data from one stage to the next.

#### **2.2. Concurrency Model**
To enhance performance and scalability for I/O-bound operations, the application uses a **hybrid `asyncio` and `ThreadPoolExecutor` model**.

*   **`asyncio` Event Loop**: The core of the application runs on a single-threaded `asyncio` event loop. This allows the program to handle tens of thousands of concurrent I/O operations (like API calls to YouTube and OpenAI) with very low overhead. All native I/O-bound tasks are implemented as `async` coroutines.

*   **`ThreadPoolExecutor` for Blocking Code**: For operations that are inherently blocking or CPU-bound (such as audio transcription with `SpeechRecognition` or synchronous file I/O from libraries like `yt-dlp`), a single `ThreadPoolExecutor` is used. The `asyncio` event loop delegates these blocking tasks to the thread pool using `loop.run_in_executor()`. This prevents the CPU-bound work from stalling the event loop, allowing I/O-bound tasks to continue running in parallel.

This hybrid approach provides the high scalability of `asyncio` for network requests while safely handling legacy or CPU-intensive synchronous code in a separate thread pool, offering the best of both worlds.

#### **2.3. Component Overview**
*   **`main.py` (Orchestrator)**: The entry point of the application. It handles configuration, sets up the directory structure, initializes all service modules, and manages the thread pool for concurrent video processing.
*   **`VideoDiscoverer` (Discoverer)**: Responsible for the high-level logic of identifying which videos need to be processed. It uses the `VideoMetadataFetcher` and `FileManager` to filter videos based on program parameters and summary existence.
*   **`VideoMetadataFetcher` (Data Access)**: A focused client for `yt-dlp`. Its sole responsibility is to fetch both lightweight and detailed video metadata from YouTube.
*   **`VideoDownloader` (Utility)**: A utility class responsible for all file downloads. It handles downloading the main video files (MP4s) and video captions (VTTs).
*   **`VideoProcessor` (Worker)**: The core component that executes the entire processing pipeline for a *single* video. It orchestrates the transcription and summarization stages.
*   **`AudioTranscriber` / `AudioExtractor` (Transcription Services)**: These modules handle the "manual" transcription fallback. `AudioExtractor` pulls the audio from a video file, and `AudioTranscriber` converts that audio into text.
*   **`AgentSummarizer` (AI Service)**: A client for the OpenAI API. It takes a text transcription and returns a generated summary, handling complexities like text chunking for long inputs.
*   **`FileManager` (Utility)**: A helper class that centralizes file system logic, such as standardizing filenames and checking for the existence of files.
*   **`Logger` (Utility)**: Configures and provides a centralized logging instance for the entire application.

---

### **3. Error Handling and Resilience**
*   **Network Errors**: All network calls (metadata fetching, video downloading, OpenAI API calls) are wrapped in `try...except` blocks to prevent application crashes and log the error.
*   **Idempotency**: The application can be run multiple times without re-processing completed videos, thanks to the summary existence check at the start of the discovery phase.
*   **Resumability**: The `VideoProcessor` checks for intermediate files (video, audio) before creating them, allowing it to resume a failed process from the last successful step.
*   **Transcription Failures**: The `AudioTranscriber` is resilient to failures in individual audio chunks, allowing a long transcription to complete even if parts of it are unintelligible.
*   **Concurrency Failures**: The main thread pool loop in `main.py` catches exceptions from child threads, ensuring that one failed video process does not terminate the others.
