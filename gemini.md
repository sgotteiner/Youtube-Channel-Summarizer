# Gemini Coding Standards and Project Documentation

This document outlines the coding standards, project structure, and best practices to be followed in this project. Adhering to these guidelines ensures the code remains clean, maintainable, and consistent.

## 1. Project Overview

The **YouTube Channel Summarizer** is a Python application designed to automate the process of fetching videos from a YouTube channel, transcribing their audio content, and generating concise summaries using AI.

### Core Pipeline:
1.  **Metadata Fetching**: Retrieves a list of the latest videos from a specified channel.
2.  **Transcription**: For each video, it either downloads existing captions or performs audio extraction and speech-to-text transcription.
3.  **Summarization**: The transcription is passed to an AI agent (OpenAI's GPT) to produce a summary.
4.  **File Management**: The application manages all intermediate files (videos, audio, transcriptions) and final summaries, with an option to clean up intermediate files.

## 2. Coding Standards

### Style Guide
-   **PEP 8**: All Python code should adhere to the [PEP 8 style guide](https://www.python.org/dev/peps/pep-0008/). Use a linter like `flake8` or an autoformatter like `black` to enforce this.
-   **Naming Conventions**:
    -   `snake_case` for variables, functions, and methods.
    -   `PascalCase` for classes.
    -   `UPPER_SNAKE_CASE` for constants.
    -   Private methods should be prefixed with a single underscore (e.g., `_private_method`).

### Docstrings and Comments
-   **PEP 257**: All modules, classes, and functions should have descriptive docstrings that follow the [PEP 257 conventions](https://www.python.org/dev/peps/pep-0257/).
-   **Clarity Over Comments**: Focus on writing clear, self-documenting code. Add comments only to explain the "why" behind complex or non-obvious logic, not the "what".
-   **Type Hinting**: Use Python's type hints for all function signatures to improve readability and allow for static analysis.

### Design Principles
-   **Single Responsibility Principle (SRP)**: Every class and function should have one, and only one, reason to change.
    -   `main.py` is for orchestration only. It should not contain business logic, conditional statements, or file manipulation.
    -   Each class should be responsible for a distinct part of the pipeline (e.g., `VideoProcessor`, `AudioTranscriber`).
-   **Function Length**: Aim to keep functions concise. As a general guideline, a function's core logic should not exceed **10-15 lines** (excluding comments, docstrings, and logging statements). If a function is longer, consider breaking it down into smaller helper functions.

## 3. Project Structure

The project is organized into modules, each with a clear responsibility.

```
.
├── AgentSummarizer.py      # Handles interaction with the OpenAI API for summarization.
├── AudioTranscriber.py     # Contains classes for audio extraction and transcription.
├── ChannelVideoDownloader.py # Manages fetching video metadata and downloading videos.
├── VideoProcessor.py       # Encapsulates the logic for processing a single video.
├── main.py                 # The main entry point and orchestrator of the pipeline.
├── logger.py               # Configures the application-wide logger.
├── requirements.txt        # Lists project dependencies.
├── gemini.md               # This file.
└── ... (directories for output)
```

## 4. Logging

-   A central logger is configured in `logger.py` and passed to the classes that need it.
-   Use descriptive log messages to provide insight into the application's state.
-   **Levels**:
    -   `INFO`: For high-level status updates (e.g., "Starting video processing").
    -   `DEBUG`: For detailed, low-level information useful for debugging.
    -   `WARNING`: For non-critical issues that should be noted (e.g., "Captions not found").
    -   `ERROR`: For errors that prevent a specific task from completing but don't halt the application.
    -   `CRITICAL`: For errors that force the application to stop.
