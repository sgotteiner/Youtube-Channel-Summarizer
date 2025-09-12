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
*   **`ChannelVideoDownloader` (Discoverer)**: Responsible for identifying which videos need to be processed. It fetches video metadata from YouTube and filters them based on program parameters and whether they have already been summarized.
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
[main.py: Read Config (channel_name, num_videos, etc.)]
   |
   v
[ChannelVideoDownloader: discover_videos]
   |
   | 1. Fetch lightweight video list (IDs, titles) from YouTube channel.
   | 2. For each video ID:
   |    - [FileManager: does_summary_exist?] -> (Skip if True)
   | 3. For remaining videos:
   |    - Fetch full metadata (duration, has_captions).
   |    - Apply filters (max_video_length if no captions).
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
   |    - (If True) -> [Download Captions (VTT)] -> [Process VTT to clean text]
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
    *   Define and manage application-level configuration parameters (`channel_name`, `num_videos_to_process`, `max_video_length`, `is_openai_runtime`, `is_save_only_summaries`).
    *   Set up the required directory structure using `setup_directories`.
    *   Initialize all service classes (`VideoDownloader`, `AudioTranscriber`, etc.) and the central logger.
    *   Instantiate `ChannelVideoDownloader` to discover videos.
    *   Create and manage a `ThreadPoolExecutor` to distribute `VideoProcessor` tasks.
    *   Wait for all tasks to complete and log any exceptions that arise from the threads.
*   **Key Logic**:
    *   **Experimental Mode**: If `is_openai_runtime` is `False`, it modifies the summaries path to point to an `experimental` subdirectory to prevent mixing test outputs with real summaries.

#### **3.2. `ChannelVideoDownloader` - Discoverer**
*   **Responsibilities**:
    *   Fetch a list of all videos from a channel.
    *   Filter out videos that have already been summarized.
    *   Apply program parameters to produce a final list of videos to process.
*   **Key Methods & Logic**:
    *   `discover_videos()`: The main entry point. It orchestrates the discovery process in an optimized order:
        1.  Calls `_get_video_entries()` for a fast, lightweight list of all videos.
        2.  Iterates through this list. For each video, it first calls `FileManager.does_summary_exist()`. If a summary exists, the video is skipped immediately.
        3.  If no summary exists, it calls `_fetch_video_details()` to get full metadata.
        4.  It then validates the video with `_is_video_valid()`.
        5.  If valid, the video is added to the `videos_to_process` list.
        6.  The loop breaks as soon as the list size reaches `num_videos_to_process`. This ensures it continues searching past already-summarized videos to find the required number of *new* videos.
    *   `_is_video_valid()`: Contains the crucial filtering logic. It checks the video's duration against `max_video_length`. The check can be configured to apply to all videos or only to videos without captions, providing flexible control over which videos are processed based on their length.

#### **3.3. `VideoProcessor` - Worker**
*   **Responsibilities**:
    *   Manage the end-to-end processing pipeline for a single video.
    *   Obtain the video's transcription using the most efficient method available.
    *   Invoke the summarizer with the transcription.
    *   Save the final summary.
    *   Clean up intermediate files.
*   **Key Methods & Logic**:
    *   `process()`: The main public method that executes the entire workflow.
    *   `_get_transcription()`: Implements the caption-first strategy. It first attempts to download captions. If that fails or is not possible, it logs a warning and calls `_transcribe_audio_from_video` as a graceful fallback.
    *   `_transcribe_audio_from_video()`: Manages the full manual transcription pipeline, checking for existing files at each step (video -> audio -> transcription) to make the process resumable if it was previously interrupted.

#### **3.4. `AudioTranscriber` - Speech-to-Text Service**
*   **Responsibilities**:
    *   Transcribe a given audio file into text.
*   **Key Methods & Logic**:
    *   `transcribe_audio()`: Takes an audio file path. It uses the `pydub` library to load the audio and splits it into 10-second chunks to avoid API limits and timeouts.
    *   `_transcribe_chunk()`: It processes each chunk individually using the `speech_recognition` library. It includes error handling for chunks that are unintelligible (`sr.UnknownValueError`) or fail due to API issues, inserting a placeholder like `[unintelligible]` without failing the entire transcription.

#### **3.5. `AgentSummarizer` - AI Service Client**
*   **Responsibilities**:
    *   Interface with the OpenAI API to generate summaries.
    *   Handle text that is too long for the model's context window.
*   **Key Methods & Logic**:
    *   `summary_call()`: The main public method. It checks if `is_openai_runtime` is `True`. If not, it returns the raw transcription for testing purposes. Otherwise, it calls `_recursive_summarize`.
    *   `_recursive_summarize()`: This method uses `tiktoken` to check the transcription's token count. If it exceeds the `CHUNK_TARGET_SIZE`, it splits the text into chunks, calls `_summarize_text` on each (with a prompt indicating it's a partial text), and then recursively calls itself on the combined summaries until the text is small enough to be summarized in a single API call.

#### **3.6. `FileManager` - File System Utility**
*   **Responsibilities**:
    *   Provide standardized filenames.
    *   Check for the existence of summary files.
*   **Key Methods & Logic**:
    *   `get_base_filename()`: Creates the standard `SanitizedTitle-DD_MM_YYYY-VideoID` filename string. It uses a static `_sanitize_filename` method to remove characters that are illegal in file paths.
    *   `does_summary_exist()`: Takes a `video_id` and uses `pathlib.Path.glob` with the pattern `*-{video_id}.txt`. This is a highly efficient way to check for existence without needing to know the full title or date.

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