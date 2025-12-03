# YouTube Channel Summarizer

## Overview

This project is a fully automated pipeline that downloads, transcribes, and summarizes YouTube videos from a specified channel. It is designed with an efficient, concurrent architecture to process multiple videos in parallel, making it suitable for summarizing entire channel backlogs or keeping up with new content.

The pipeline is composed of distinct, modular stages:
1.  **Video Discovery:** Finds the latest videos from the channel that haven't been processed.
2.  **Audio Download:** Downloads audio directly from YouTube videos (optimization: skips video download when possible).
3.  **Transcription:** Converts the audio into text.
4.  **Summarization:** Uses an AI agent (OpenAI) to generate a concise summary of the transcription.

The system includes a robust fallback mechanism: if OpenAI processing fails due to rate limits or other issues, the original transcription is automatically preserved as the summary to ensure no data loss.

## Setup

Follow these steps to set up the project environment.

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd Youtube-Channel-Summarizer
```

### 2. Create a Virtual Environment
It is highly recommended to use a virtual environment to manage project dependencies.
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

### 3. Install Dependencies
Install all the required Python packages using the `requirements.txt` file.
```bash
pip install -r requirements.txt
```

### 4. Configure the Application
The application is configured using a `.config` file in the root directory. Create this file and add the following settings. You can adjust these values to fit your needs.

**Example `.config` file:**
```ini
# The name of the YouTube channel you want to process
CHANNEL_NAME="Tech With Tim"

# The number of recent videos to check and process
NUM_VIDEOS_TO_PROCESS=2

# The maximum video length in minutes. Videos longer than this will be skipped.
MAX_VIDEO_LENGTH=10

# If True, intermediate files (videos, audio, transcriptions) will be deleted after processing,
# leaving only the final summaries.
IS_SAVE_ONLY_SUMMARIES=True

# If True, the MAX_VIDEO_LENGTH limit only applies to videos that do not have captions.
# This is useful for skipping long, music-only videos that can't be transcribed.
APPLY_MAX_LENGTH_FOR_CAPTIONLESS_ONLY=True

# Set to True if you are running in an environment with an OpenAI API key.
# If you have an OpenAI API key, create a .env file and add your key like this:
# OPENAI_API_KEY="your-key-here"
IS_OPENAI_RUNTIME=True
```

If you are using OpenAI for summarization, create a `.env` file in the root directory and add your API key:
```
OPENAI_API_KEY="your-secret-api-key"
```

## Usage

Once the setup is complete, you can run the entire pipeline by executing the `main.py` script:

```bash
python src/main.py
```

The application will start processing the videos based on your configuration. Logs will be printed to the console and saved to `processing.log`.