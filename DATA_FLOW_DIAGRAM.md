## **Data Flow Diagram: YouTube Channel Summarizer**

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
[FileManager: cleanup_intermediate_files (if enabled)]
   |
   v
[End of Thread]
```
