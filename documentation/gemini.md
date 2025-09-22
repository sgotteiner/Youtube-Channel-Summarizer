# Gemini Coding Standards and Project Documentation

This document outlines the coding standards and a high-level overview of the YouTube Channel Summarizer project. Adhering to these guidelines ensures the code remains clean, maintainable, and consistent.

## 1. Project Overview

The **YouTube Channel Summarizer** is a Python application designed to automate the process of fetching videos from a YouTube channel, transcribing their audio content, and generating concise summaries using AI. The system is built to be efficient and resilient, prioritizing existing captions over manual transcription and handling long videos through chunking.

For a complete breakdown of the architecture, component design, data flow, and detailed operational logic, please refer to the **[SOFTWARE_DESIGN_DOCUMENT.md](SOFTWARE_DESIGN_DOCUMENT.md)**.

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
-   **Don't Repeat Yourself (DRY)**: Avoid duplicating code. If you find the same logic implemented in multiple places, refactor it into a single, reusable function or class. This makes the code easier to maintain, as changes only need to be made in one location.
-   **Function Length**: Aim to keep functions concise. As a general guideline, a function's core logic should not exceed **10-15 lines** (excluding comments, docstrings, and logging statements). If a function is longer, consider breaking it down into smaller helper functions.
-   **File and Class Granularity**: Keep files focused and small. If a file contains multiple classes that can be logically separated, it is preferable to split them into their own files. This improves maintainability and makes the codebase easier for developers and AI-based coding tools to navigate, as it reduces the amount of context needed to understand any single file.

### **Important**: Preserving Manual Edits
-   If a function or block of code is preceded by a comment containing `NO AI EDITS`, it must not be altered in any way. This indicates a specific, intentional implementation that should be preserved.
