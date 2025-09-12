## **Software Design Document: YouTube Channel Summarizer**

**Version:** 1.0
**Date:** September 10, 2025

### **1. Introduction**

#### **1.1. Purpose**
This document provides a detailed design for the YouTube Channel Summarizer application. It covers the system architecture, high-level and low-level design of each component, data flow, and core logic. This document is intended for developers and stakeholders to understand the system's internal workings.

#### **1.2. Scope**
The application is designed to automate the process of fetching videos from a specified YouTube channel, transcribing their audio content, and generating concise summaries using the OpenAI API. It is a command-line application intended to be run as a script.

#### **1.3. System Overview**
The YouTube Channel Summarizer is a Python application that operates as a pipeline. It identifies new videos on a channel, processes them to get a text transcription (either by downloading existing captions or by performing speech-to-text on the audio), and then uses an AI agent to summarize the transcription. The system is designed to be resilient, efficient, and configurable, with a focus on minimizing redundant work and managing costs.

---

### **2. System Architecture (High-Level Design)**

#### **2.1. Architectural Style**
The system employs a **modular, pipeline-driven architecture**. Each distinct responsibility (e.g., downloading, transcribing, summarizing) is encapsulated within its own class. A central orchestrator (`main.py`) initializes these components and manages the overall workflow, passing data from one stage to the next.

#### **2.2. Concurrency Model**
To enhance performance, the application processes multiple videos in parallel. It uses a **`concurrent.futures.ThreadPoolExecutor`** to manage a pool of worker threads. Each thread is assigned a single video to process, executing the entire pipeline for that video independently. This allows I/O-bound tasks like downloading and API calls for different videos to occur simultaneously.

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

#### **2.4. Data Flow Diagram**
```
[Start]
   |
   v
[main.py: Read Config, Initialize Services]
   |
   v
[VideoDiscoverer: discover_videos]
   |
   | 1. [VideoMetadataFetcher: get_video_entries] -> Get lightweight list of all video IDs.
   | 2. For each video ID:
   |    - [FileManager: does_summary_exist?] -> (Skip if True)
   | 3. For remaining videos:
   |    - [VideoMetadataFetcher: fetch_video_details] -> Get full metadata.
   |    - Apply filters (max_video_length, etc.).
   |
   v
[List of valid videos to process]
   |
   v
[main.py: ThreadPoolExecutor]
   |
   `-----> [VideoProcessor 1: process()] for Video 1
   `-----> [VideoProcessor 2: process()] for Video 2
   `-----> ...

----------------- Inside a single VideoProcessor thread -----------------
[VideoProcessor: _get_transcription]
   |
   | 1. Check if video `has_captions`.
   |    - (If True) -> [VideoDownloader: download_captions] -> [Process VTT to clean text]
   |    - (If False or Caption Download Fails) -> Fallback:
   |        a. [VideoDownloader: download_video]
   |        b. [AudioExtractor: extract_audio]
   |        c. [AudioTranscriber: transcribe_audio (in chunks)]
   |
   v
[Transcription Text]
   |
   v
[AgentSummarizer: summary_call]
   |
   | 1. Check token count of transcription.
   | 2. (If too long) -> Split into chunks, summarize each, combine, and summarize again.
   | 3. (If short enough) -> Summarize directly.
   |
   v
[Summary Text]
   |
   v
[FileManager: Save summary to .txt file]
   |
   v
[VideoProcessor: _cleanup_intermediate_files (if enabled)]
   |
   v
[End of Thread]
```

---

### **3. Module Design (Low-Level Design)**

#### **3.1. `main.py` - Orchestrator**
*   **Responsibilities**:
    *   Define and manage application-level configuration parameters.
    *   Set up the required directory structure.
    *   Initialize all service classes (`VideoMetadataFetcher`, `VideoDiscoverer`, `VideoDownloader`, etc.).
    *   Instantiate `VideoDiscoverer` to find videos.
    *   Create and manage a `ThreadPoolExecutor` to distribute `VideoProcessor` tasks.
    *   Wait for all tasks to complete and log any exceptions.
*   **Key Logic**:
    *   **Experimental Mode**: If `is_openai_runtime` is `False`, it modifies the summaries path to point to an `experimental` subdirectory.

#### **3.2. `VideoDiscoverer` - Discoverer**
*   **Responsibilities**:
    *   Orchestrate the discovery of new videos to be processed.
    *   Filter videos based on whether a summary already exists.
    *   Validate videos against program parameters like maximum length.
*   **Key Methods & Logic**:
    *   `discover_videos()`: The main entry point. It gets a lightweight list of video entries from the `VideoMetadataFetcher`. It then iterates through them, using the `FileManager` to check for existing summaries and the `VideoMetadataFetcher` to get full details for new videos before validating them.
    *   `_is_video_valid()`: Contains the filtering logic to check a video's duration against the configured `max_video_length`.

#### **3.3. `VideoMetadataFetcher` - Data Access**
*   **Responsibilities**:
    *   Act as the sole interface to `yt-dlp` for fetching metadata.
    *   Retrieve a lightweight list of all video entries for a channel.
    *   Fetch full, detailed metadata for a single video ID.
*   **Key Methods & Logic**:
    *   `get_video_entries()`: Uses `yt-dlp` with the `extract_flat` option to quickly get a list of all video IDs and titles.
    *   `fetch_video_details()`: Uses `yt-dlp` to get a rich metadata object for a single video, including duration, upload date, and caption availability.
    *   `_parse_video_info()`: A private helper to transform the raw `yt-dlp` dictionary into the application's standard `video_data` format.

#### **3.4. `VideoDownloader` - Downloader Utility**
*   **Responsibilities**:
    *   Handle all file downloads from YouTube.
*   **Key Methods & Logic**:
    *   `download_video()`: Downloads the full MP4 video file for a given URL using `pytubefix`.
    *   `download_captions()`: Downloads the English VTT caption file for a given video ID using `yt-dlp`.

#### **3.5. `VideoProcessor` - Worker**
*   **Responsibilities**:
    *   Manage the end-to-end processing pipeline for a single video.
    *   Obtain the video's transcription using the most efficient method available.
    *   Invoke the summarizer with the transcription.
    *   Save the final summary and clean up intermediate files.
*   **Key Methods & Logic**:
    *   `process()`: The main public method that executes the entire workflow.
    *   `_get_transcription()`: Implements the caption-first strategy. It calls the `VideoDownloader` service to get captions. If that fails, it falls back to the manual audio transcription pipeline.
    *   `_transcribe_audio_from_video()`: Manages the fallback process: `VideoDownloader` -> `AudioExtractor` -> `AudioTranscriber`. It checks for existing files at each step to make the process resumable.

#### **3.6. `AudioTranscriber` - Speech-to-Text Service**
*   **Responsibilities**:
    *   Transcribe a given audio file into text.
*   **Key Methods & Logic**:
    *   `transcribe_audio()`: Uses `pydub` to split a long audio file into manageable chunks.
    *   `_transcribe_chunk()`: Processes each chunk with the `speech_recognition` library, with error handling for unintelligible audio.

#### **3.7. `AgentSummarizer` - AI Service Client**
*   **Responsibilities**:
    *   Interface with the OpenAI API to generate summaries.
    *   Handle text that is too long for the model's context window.
*   **Key Methods & Logic**:
    *   `summary_call()`: The main public method. Returns the raw transcription if `is_openai_runtime` is `False`.
    *   `_recursive_summarize()`: Uses `tiktoken` to check the transcription's token count. If it's too long, it splits the text, summarizes the chunks, and recursively calls itself on the combined summaries.

#### **3.8. `FileManager` - File System Utility**
*   **Responsibilities**:
    *   Provide standardized filenames.
    *   Check for the existence of summary files.
*   **Key Methods & Logic**:
    *   `get_base_filename()`: Creates the standard `SanitizedTitle-DD_MM_YYYY-VideoID` filename string.
    *   `does_summary_exist()`: Uses `pathlib.Path.glob` with a `*-{video_id}.txt` pattern for efficient existence checks.

---

### **4. Data Design**

#### **4.1. Data Structures**
*   **`video_data` Dictionary**: The primary data structure passed between components. It's a dictionary containing all relevant metadata for a video.
    ```python
    {
        "video_url": str,
        "video_id": str,
        "video_title": str,
        "duration": int,      # in seconds
        "upload_date": str,   # "DD_MM_YYYY"
        "has_captions": bool
    }
    ```

#### **4.2. Directory Structure**
The application creates a structured set of directories to keep all artifacts organized by channel name.
```
./
├── channel_videos/{channel_name}/         # Downloaded .mp4 files
├── channel_audios/{channel_name}/         # Extracted .wav files
├── channel_transcriptions/{channel_name}/ # Generated .txt transcriptions
└── channel_summaries/{channel_name}/      # Final .txt summaries
    └── experimental/                      # Summaries from non-AI runs
```

---

### **5. Error Handling and Resilience**
*   **Network Errors**: All network calls (metadata fetching, video downloading, OpenAI API calls) are wrapped in `try...except` blocks to prevent application crashes and log the error.
*   **Idempotency**: The application can be run multiple times without re-processing completed videos, thanks to the summary existence check at the start of the discovery phase.
*   **Resumability**: The `VideoProcessor` checks for intermediate files (video, audio) before creating them, allowing it to resume a failed process from the last successful step.
*   **Transcription Failures**: The `AudioTranscriber` is resilient to failures in individual audio chunks, allowing a long transcription to complete even if parts of it are unintelligible.
*   **Concurrency Failures**: The main thread pool loop in `main.py` catches exceptions from child threads, ensuring that one failed video process does not terminate the others.

---

### **6. Key Dependencies**
The application relies on several external libraries, which are managed in `requirements.txt`.
*   **`yt-dlp`**: The core library for interacting with YouTube. Used for fetching both lightweight and detailed video metadata, and for downloading captions.
*   **`pytubefix`**: A library for downloading YouTube video streams. Used in the fallback manual transcription process to download the full MP4 video.
*   **`openai`**: The official client for the OpenAI API. Used to send transcriptions for summarization.
*   **`python-dotenv`**: Used to load the `OPENAI_API_KEY` from a `.env` file.
*   **`tiktoken`**: Used for accurately counting tokens in a transcription to determine if it needs to be chunked before sending to the OpenAI API.
*   **`SpeechRecognition`**: The primary library for converting audio to text. It acts as a wrapper for various speech recognition engines.
*   **`pydub`**: A library for audio manipulation. Used to split long audio files into smaller chunks for reliable transcription.
*   **`moviepy`**: A library for video editing. Used to extract the audio track from a downloaded MP4 file.

---

### **7. Configuration and Execution**

#### **7.1. Configuration**
The application's configuration is loaded at startup by `main.py` from two files in the project root:
1.  `.env`: This file is intended for secrets, primarily the `OPENAI_API_KEY`.
2.  `.config`: This file contains all other operational settings, such as the target channel and video length limits.

The `python-dotenv` library is used to load both files into the environment. `main.py` loads `.env` first, then `.config`. This allows environment variables to take precedence over file-based configurations. The `Config` class in `config.py` then reads these environment variables, providing a single, validated source of settings for the rest of the application.

Key parameters in the `.config` file:
*   `CHANNEL_NAME` (str): The name or handle of the target YouTube channel.
*   `NUM_VIDEOS_TO_PROCESS` (int, optional): The maximum number of *new* videos to process.
*   `MAX_VIDEO_LENGTH` (int, optional): The maximum duration in minutes for a video to be processed.
*   `APPLY_MAX_LENGTH_FOR_CAPTIONLESS_ONLY` (bool): Controls whether `MAX_VIDEO_LENGTH` applies to all videos or only those without captions.
*   `IS_OPENAI_RUNTIME` (bool): Toggles real OpenAI API calls.
*   `IS_SAVE_ONLY_SUMMARIES` (bool): Toggles the deletion of intermediate files.

#### **7.2. Setup**
1.  **Install Dependencies**: Run `pip install -r requirements.txt`.
2.  **Create `.env` file**: Create a `.env` file in the project root for your API key: `OPENAI_API_KEY="your_key_here"`.
3.  **Create `.config` file**: Create a `.config` file to customize settings. You can copy the keys from the example in this document.

#### **7.3. Execution**
The application is executed by running the main script from the command line:
```bash
python main.py
```
Logs will be written to `processing.log` in the root directory.